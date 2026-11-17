"""Two-layer LLM vehicle: LLM planner (event-triggered) + IDM executor.

Design (maps onto the Speed Planning / Speed Tracking structure from the
Gipps lecture):

    Upper layer  LLMClient.decide()      -> target speed + time headway
                                          (cached between event triggers)
    Lower layer  IDMVehicle acceleration -> computed every 0.1 s step with
                                          the cached plan as its desired
                                          speed / headway

The LLM is never allowed to command acceleration directly, so control
stability and the collision-avoidance term stay with the validated IDM
rule. If the LLM call fails, the vehicle keeps its previous plan (or the
plain config defaults) — graceful degradation.

Event triggers (from the teacher's hint: "cached or event-triggered policy"):
    1. periodic refresh at most every ``max_recheck_interval`` seconds
    2. approaching an active bottleneck (within ``notice_distance`` metres)
    3. entering or leaving the bottleneck zone
    4. closing fast on the leader (relative speed above threshold) or gap
       below the emergency threshold
Calls are additionally spaced by ``min_call_interval`` seconds to avoid
call storms.
"""

import math
import time

from noise import normal as _det_normal
from vehicle_idm import IDMVehicle


class LLMVehicle(IDMVehicle):
    """IDM executor whose desired speed and headway are set by an LLM."""

    def __init__(self, config, vehicle_id, vehicle_front=None, llm_client=None,
                 min_call_interval=2.0, max_recheck_interval=15.0,
                 notice_distance=300.0, log_decisions=True):
        super().__init__(config, vehicle_id, vehicle_front)

        self.llm_client = llm_client

        # Cached planner output (None = use plain config/IDM defaults).
        self.llm_target_speed = None
        self.llm_time_headway = config.idm_time_headway

        # The executor applies headway INCREASES gradually (0.5 s per
        # second). An instant bump would discontinuously inflate the IDM
        # desired gap and trigger needless hard braking; real ACC systems
        # rate-limit target changes for exactly this reason. Decreases are
        # applied immediately because they shrink the desired gap, which is
        # the safe direction.
        self.headway_ramp_rate = 0.5        # (s headway) / (s time)
        self.effective_headway = config.idm_time_headway

        # Trigger policy parameters (tunable: real APIs need wider spacing).
        self.min_call_interval = min_call_interval       # s between calls
        self.max_recheck_interval = max_recheck_interval  # s periodic refresh
        self.notice_distance = notice_distance            # m look-ahead
        self.emergency_gap = 10.0          # m, ask planner when this close
        self.emergency_relative_speed = 3.0  # m/s, closing fast on leader

        # Bookkeeping for the report.
        self.current_time = 0.0
        self.inside_bottleneck = False
        self.bottleneck_active_now = False
        self.entered_bottleneck_now = False
        self.exited_bottleneck_now = False
        self._was_inside = False
        self.call_count = 0
        self.failure_count = 0
        self.last_llm_time = -math.inf
        # In a 589-vehicle full-fleet run every vehicle replans hundreds of
        # times; keeping every entry with its observation would hold
        # millions of dicts in memory. Only the tracked ego stores the full
        # log, and even that is capped.
        self.log_decisions = log_decisions
        self.max_log_entries = 400
        self.decision_log = []
        self.latency_log = []

        # Separate what the planner ASKED for, what the planner guardrails
        # stored as the cached plan, and what the executor actually applied.
        # Without this three-way split a decision log cannot tell a bad model
        # output from a guardrail override or an executor override.
        self.guardrail_corrections = 0        # cached plan != model output
        self.recovery_guard_activations = 0   # cached slow plan lifted past z_end
        self.executor_steps = 0
        self.road_limit_cap_steps = 0         # cached plan ABOVE the road limit
        self.headway_ramp_steps = 0           # headway still ramping up
        self.stop_intent_steps = 0            # target speed <= 0 branch
        self.executor_target_speed = None     # what the IDM layer was given
        self.executor_target_headway = config.idm_time_headway
        self.model_name = getattr(llm_client, "model", None) or getattr(
            llm_client, "name", None
        )
        self.prompt_version = getattr(llm_client, "PROMPT_VERSION", None)
        # Per-second execution trace for the tracked ego: the report needs
        # to separate "the model said X" from "the vehicle did Y".
        self.execution_trace = []
        self.max_trace_entries = 2000
        self.trace_interval = 1.0
        self._last_trace_time = -math.inf

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------
    def check_road(self, current_time):
        """Extend the base road check with planner bookkeeping."""
        super().check_road(current_time)
        self.current_time = current_time
        self.bottleneck_active_now = (
            self.bottleneck_t_start <= current_time < self.bottleneck_t_end
        )
        inside = self.bottleneck_x_start <= self.position <= self.bottleneck_x_end
        self.inside_bottleneck = inside
        self.entered_bottleneck_now = inside and not self._was_inside
        self.exited_bottleneck_now = (not inside) and self._was_inside
        self._was_inside = inside

    def get_planner_observation(self):
        """Compact JSON-ready view of the situation the LLM plans for."""
        leader = self.vehicle_front
        gap = None
        relative_speed = None
        leader_speed = None
        if leader is not None and leader.active:
            gap = max(leader.position - self.position - self.vehicle_length, 0.0)
            relative_speed = self.speed - leader.speed
            leader_speed = leader.speed

        return {
            "vehicle_id": self.id,
            "time": round(self.current_time, 1),
            "speed": round(self.speed, 2),
            "current_speed_limit": self.current_speed_limit,
            "bottleneck_active": self.bottleneck_active_now,
            "inside_bottleneck": self.inside_bottleneck,
            "distance_to_bottleneck_start": round(
                self.bottleneck_x_start - self.position, 1
            ),
            "distance_to_bottleneck_end": round(
                self.bottleneck_x_end - self.position, 1
            ),
            "gap": None if gap is None else round(gap, 1),
            "relative_speed": None if relative_speed is None else round(relative_speed, 2),
            "leader_speed": None if leader_speed is None else round(leader_speed, 2),
        }

    # ------------------------------------------------------------------
    # Planner interaction
    # ------------------------------------------------------------------
    def _should_call_planner(self):
        if self.llm_client is None:
            return False
        since_call = self.current_time - self.last_llm_time
        if since_call < self.min_call_interval:
            return False
        if since_call >= self.max_recheck_interval:
            return True
        distance_to_bottleneck = self.bottleneck_x_start - self.position
        if (
            self.bottleneck_active_now
            and 0.0 <= distance_to_bottleneck <= self.notice_distance
        ):
            return True
        if self.entered_bottleneck_now or self.exited_bottleneck_now:
            return True
        leader = self.vehicle_front
        if leader is not None and leader.active:
            gap = leader.position - self.position - self.vehicle_length
            relative_speed = self.speed - leader.speed
            if gap < self.emergency_gap:
                return True
            if relative_speed > self.emergency_relative_speed:
                return True
        return False

    @staticmethod
    def validate_plan(decision):
        """Validate an LLM decision; return (target, headway, error).

        The model reply crosses a system boundary, so it is fully checked:
        right type, required fields, convertible to float, finite (NaN/inf
        rejected — a NaN would otherwise pass float() and then be silently
        clamped into a full-speed command by min/max).
        """
        if not isinstance(decision, dict):
            return None, None, "non-dict decision: %s" % type(decision).__name__
        try:
            target = float(decision["target_speed"])
            headway = float(decision["time_headway"])
        except KeyError as exc:
            return None, None, "missing field %s" % exc
        except (TypeError, ValueError) as exc:
            return None, None, "non-numeric field: %s" % exc
        if not (math.isfinite(target) and math.isfinite(headway)):
            return None, None, "non-finite value (NaN/inf)"
        return target, headway, None

    def _record_decision(self, entry):
        """Append a decision-log entry if this vehicle is being traced."""
        if self.log_decisions and len(self.decision_log) < self.max_log_entries:
            self.decision_log.append(entry)

    def _call_planner(self):
        observation = self.get_planner_observation()
        started = time.perf_counter()
        decision = None
        error = None
        try:
            decision = self.llm_client.decide(observation)
        except Exception as exc:
            error = "exception: %s" % exc
        latency = time.perf_counter() - started

        self.last_llm_time = self.current_time
        self.call_count += 1
        self.latency_log.append(latency)

        if error is None:
            target, headway, error = self.validate_plan(decision)

        if error is not None:
            # Explicit fallback: keep the previous cached plan
            # (fail-operational; the IDM executor keeps the car safe).
            self.failure_count += 1
            self._record_decision(
                {
                    "t": round(self.current_time, 1),
                    "status": "invalid",
                    "error": error,
                    "raw": repr(decision)[:200],
                    "latency_s": round(latency, 3),
                    "observation": observation if self.log_decisions else None,
                }
            )
            return

        # Guardrails: the planner may only slow down within the road limit
        # and pick a sane headway; it can never command a higher speed than
        # the road allows or unsafe headways.
        requested_target = target
        requested_headway = headway
        target = max(0.0, min(target, self.current_speed_limit))
        headway = max(0.8, min(headway, 2.0))
        corrected = (
            not math.isclose(target, requested_target, abs_tol=1e-9)
            or not math.isclose(headway, requested_headway, abs_tol=1e-9)
        )
        if corrected:
            self.guardrail_corrections += 1

        self.llm_target_speed = target
        self.llm_time_headway = headway
        self._record_decision(
            {
                "t": round(self.current_time, 1),
                "status": "ok",
                # Model output (as returned after parsing, before clamping).
                "requested_target_speed": round(requested_target, 2),
                "requested_time_headway": round(requested_headway, 2),
                # Plan actually handed to the executor (post-guardrail).
                # The executor may still ramp the headway or cap the speed;
                # those overrides are counted separately on the vehicle.
                "target_speed": round(target, 2),
                "time_headway": round(headway, 2),
                "guardrail_correction": corrected,
                "reason": decision.get("reason", ""),
                "latency_s": round(latency, 3),
                "observation": observation if self.log_decisions else None,
            }
        )

    # ------------------------------------------------------------------
    # Motion (called by the simulator every time step)
    # ------------------------------------------------------------------
    def _stop_acceleration(self):
        """Acceleration for an explicit stop intent (target_speed == 0).

        The IDM free-flow term divides by the desired speed, so a zero
        target would raise ZeroDivisionError; substituting a tiny epsilon
        would instead produce maximum braking as if approaching a speed
        cliff — not what "stop" means. The free-flow term is therefore
        replaced by a comfortable deceleration to standstill, while the IDM
        interaction term is kept unchanged so a close or slow leader still
        forces harder braking.
        """
        free_accel = -min(
            self.comfortable_deceleration,
            self.speed / max(self.time_step, 1e-9),
        )
        interaction = 0.0
        leader = self.vehicle_front
        if leader is not None and leader.active:
            gap = max(leader.position - self.position - self.vehicle_length, 0.1)
            step_index = int(round(self.current_time / self.time_step))
            perceived_rel = (self.speed - leader.speed) + (
                _det_normal(self.noise_seed, self.id, step_index, salt=23)
                * self.relative_speed_noise
            )
            braking_term = (
                self.speed
                * perceived_rel
                / (
                    2.0
                    * math.sqrt(
                        self.maximum_acceleration * self.comfortable_deceleration
                    )
                )
            )
            desired_gap = max(
                self.minimum_spacing + self.speed * self.time_headway + braking_term,
                self.minimum_spacing,
            )
            interaction = -self.maximum_acceleration * (desired_gap / gap) ** 2
        accel = free_accel + interaction
        return max(-self.maximum_deceleration, min(self.maximum_acceleration, accel))

    def update_acceleration(self):
        """Upper layer decides when to replan; lower layer is the IDM rule."""
        if self._should_call_planner():
            self._call_planner()

        # --- Executor stage 1: recovery guard -----------------------------
        # Once past the zone END the road limit is the full limit again
        # (Vehicle.check_road only applies the zone limit inside
        # [x_start, x_end]), so a cached slow plan must be lifted. This is
        # spatial, not time-based: it also covers experiments 3/4 where the
        # bottleneck stays time-active until the end of the run. Raising the
        # *desired* speed is still safe in a queue because the IDM
        # interaction term enforces the leader constraint below.
        recovery_applied = False
        if (
            self.position > self.bottleneck_x_end
            and self.llm_target_speed is not None
            and self.llm_target_speed < self.current_speed_limit - 1e-9
        ):
            # Counted only when it actually RAISES a stale plan, not on
            # every step past the zone end.
            self.llm_target_speed = self.current_speed_limit
            self.recovery_guard_activations += 1
            recovery_applied = True

        # --- Executor stage 2: road-limit cap -----------------------------
        # Only a cached plan ABOVE the road limit is an executor override.
        # A planner that recommends a low speed (e.g. 2 m/s in a jam) is
        # doing its job, not being overruled, and must not be counted here.
        road_limit_capped = (
            self.llm_target_speed is not None
            and self.llm_target_speed > self.current_speed_limit + 1e-9
        )
        effective_limit = self.current_speed_limit
        if self.llm_target_speed is not None:
            effective_limit = min(effective_limit, self.llm_target_speed)

        # --- Executor stage 3: headway ramp -------------------------------
        if self.llm_time_headway <= self.effective_headway:
            self.effective_headway = self.llm_time_headway
        else:
            growth = self.headway_ramp_rate * self.time_step
            self.effective_headway = min(
                self.llm_time_headway,
                self.effective_headway + growth,
            )
        self.time_headway = self.effective_headway
        headway_ramping = (
            self.effective_headway < self.llm_time_headway - 1e-9
        )

        self.executor_steps += 1
        if road_limit_capped:
            self.road_limit_cap_steps += 1
        if headway_ramping:
            self.headway_ramp_steps += 1
        self.executor_target_speed = effective_limit
        self.executor_target_headway = self.effective_headway

        if effective_limit <= 0.0:
            # Explicit stop intent: IDM cannot express a zero desired speed.
            self.stop_intent_steps += 1
            self.acceleration = self._stop_acceleration()
            self._record_execution_trace(
                effective_limit, headway_ramping, road_limit_capped,
                recovery_applied,
            )
            return

        # Feed the cached plan into the untouched teacher IDM rule.
        saved_limit = self.current_speed_limit
        self.current_speed_limit = effective_limit
        super().update_acceleration()
        self.current_speed_limit = saved_limit
        self._record_execution_trace(
            effective_limit, headway_ramping, road_limit_capped,
            recovery_applied,
        )

    def _record_execution_trace(self, effective_limit, headway_ramping,
                                road_limit_capped, recovery_applied):
        """Keep a 1 s trace of model request vs executed target (ego only)."""
        if not self.log_decisions:
            return
        if len(self.execution_trace) >= self.max_trace_entries:
            return
        if self.current_time - self._last_trace_time < self.trace_interval - 1e-9:
            return
        self._last_trace_time = self.current_time
        self.execution_trace.append(
            {
                "t": round(self.current_time, 1),
                "speed": round(self.speed, 2),
                # Cached plan (post-guardrail, pre-executor).
                "cached_target_speed": (
                    None if self.llm_target_speed is None
                    else round(self.llm_target_speed, 2)
                ),
                "cached_time_headway": round(self.llm_time_headway, 3),
                # What the executor actually handed to the IDM layer.
                "executor_target_speed": round(effective_limit, 2),
                "executor_time_headway": round(self.effective_headway, 3),
                "recovery_guard_applied": recovery_applied,
                "road_limit_capped": road_limit_capped,
                "headway_ramping": headway_ramping,
                "stop_intent": effective_limit <= 0.0,
                "acceleration": round(self.acceleration, 3),
                "decision_count_so_far": self.call_count,
            }
        )
