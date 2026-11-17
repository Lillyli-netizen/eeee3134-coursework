"""Single-layer ablation: the LLM commands acceleration directly.

This exists only as a comparison baseline for the report. It removes the
IDM executor entirely, so nothing guarantees collision avoidance between
LLM calls; the raw command is simply held until the next event trigger.

Note: once vehicles overlap, the pair ordering no longer has a physical
following relationship. The metrics layer records the first overlap time
and flags the run ``overlap_invalid``; a negative gap after that is a
symptom of the overlap, not a measure of "collision severity".
"""

import math

from vehicle_llm import LLMVehicle


class LLMDirectVehicle(LLMVehicle):
    """Raw LLM acceleration controller (no IDM safety layer)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.direct_acceleration = 0.0

    def update_acceleration(self):
        if self._should_call_planner():
            observation = self.get_planner_observation()

            decision = None
            error = None
            try:
                decision = self.llm_client.decide_acceleration(observation)
            except Exception as exc:
                error = "exception: %s" % exc

            self.last_llm_time = self.current_time
            self.call_count += 1

            if error is None:
                try:
                    accel = float(decision["acceleration"])
                except (KeyError, TypeError, ValueError) as exc:
                    accel, error = None, "bad acceleration field: %s" % exc
                else:
                    if not math.isfinite(accel):
                        accel, error = None, "non-finite acceleration"

            if error is not None:
                self.failure_count += 1
                self.decision_log.append(
                    {
                        "t": round(self.current_time, 1),
                        "status": "invalid",
                        "error": error,
                        "raw": repr(decision)[:200],
                        "observation": observation,
                    }
                )
            else:
                accel = max(
                    -self.maximum_deceleration,
                    min(accel, self.maximum_acceleration),
                )
                self.direct_acceleration = accel
                self.decision_log.append(
                    {
                        "t": round(self.current_time, 1),
                        "status": "ok",
                        "acceleration": accel,
                        "reason": decision.get("reason", ""),
                        "observation": observation,
                    }
                )

        self.acceleration = self.direct_acceleration
