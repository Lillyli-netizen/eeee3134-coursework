"""The main simulation loop."""

import random

from vehicle_idm import IDMVehicle
from vehicle_llm import LLMVehicle


class Simulator:
    def __init__(self, config, vehicle_class=IDMVehicle, llm_client=None,
                 llm_ego_id=None, llm_trigger_params=None, llm_fraction=None):
        self.config = config
        self.vehicle_class = vehicle_class
        self.llm_client = llm_client
        # Mixed traffic modes:
        #   llm_ego_id: if set, ONLY that vehicle id is LLM-controlled.
        #   llm_fraction: if set (e.g. 0.2), every Nth vehicle is LLM.
        #   Neither: every vehicle uses vehicle_class.
        self.llm_ego_id = llm_ego_id
        self.llm_fraction = llm_fraction
        self.llm_trigger_params = llm_trigger_params or {}
        self.vehicles = []

        # Fair-comparison change: the demand (arrival schedule) is generated
        # ONCE per (experiment, seed) from a dedicated RNG stream, before any
        # strategy runs. Every control strategy then faces exactly the same
        # arrival times; the entry rule only decides whether the road can
        # physically accept the vehicle at that moment.
        self.arrival_schedule = self._build_arrival_schedule()
        self.next_arrival_index = 0
        # Road-side queue log: one entry per admitted vehicle.
        self.entry_log = []   # {id, scheduled_arrival, entry_time, entry_delay}
        # Admission attempts that failed, with the blocking cause and the
        # state of the vehicle blocking the entrance. This is the evidence
        # needed to explain entry backlogs WITHOUT assuming a cause: it
        # records whether the entrance was blocked by the spacing rule or by
        # the kinematic rule, where the blocking vehicle was, how fast it was
        # going, and whether the bottleneck was active at that moment.
        self.admission_blocks = []
        self.max_admission_blocks = 20000

    def _build_arrival_schedule(self):
        """Pre-generate scheduled arrival times for the whole run."""
        cfg = self.config
        # Dedicated stream: isolated from perception noise and from anything
        # a strategy might draw. String seed keeps it stable across runs.
        rng = random.Random("arrival-%d-%d" % (cfg.seed, cfg.experiment))
        times = [0.0]
        t = 0.0
        while True:
            interval = cfg.vehicle_min_interval
            if cfg.vehicle_extra_interval > 0:
                interval += rng.expovariate(1.0 / cfg.vehicle_extra_interval)
            t += interval
            if t > cfg.time_max:
                break
            times.append(t)
        return times

    def run(self, verbose=True):
        """Generate vehicles and update their states one time step at a time."""
        time_step = self.config.time_step
        number_of_steps = int(round(self.config.time_max / time_step))

        for step in range(number_of_steps):
            current_time = step * time_step

            if verbose and step > 0 and step % int(100 / time_step) == 0:
                print(f"step: {step}, time: {current_time:.0f}")

            # 1. Admit scheduled vehicles whose arrival time has been reached.
            self._admit_vehicles(current_time)

            active_vehicles = [vehicle for vehicle in self.vehicles if vehicle.active]

            # 2. Set the desired speed from the current road conditions.
            for vehicle in active_vehicles:
                vehicle.check_road(current_time)

            # 3. Calculate all accelerations before changing any vehicle state.
            for vehicle in active_vehicles:
                vehicle.update_acceleration()

            # 4. Update all speeds and positions.
            for vehicle in active_vehicles:
                vehicle.update_motion()

            # 5. Record only vehicles that are still on the road, plus the
            # final state of a vehicle that has just reached the road end.
            next_time = (step + 1) * time_step
            for vehicle in active_vehicles:
                vehicle.record_state(next_time)

        if verbose:
            inflow_rate = len(self.vehicles) / self.config.time_max * 3600
            print(f"\nVehicle number: {len(self.vehicles)}")
            print(f"Average admitted inflow: {inflow_rate:.0f} veh/h\n")

    def _admit_vehicles(self, current_time):
        """Admit scheduled arrivals; queue them off-road when entry is unsafe.

        A scheduled vehicle that cannot enter stays at the head of the
        demand queue and is retried every step (road-side queueing, the
        simulation analogue of ramp metering). Its waiting time is logged,
        so delayed demand is never silently dropped from the comparison.
        """
        while self.next_arrival_index < len(self.arrival_schedule):
            scheduled = self.arrival_schedule[self.next_arrival_index]
            if scheduled > current_time + 1e-12:
                break
            vehicle, reason = self._try_spawn(current_time, scheduled)
            if vehicle is None:
                self._log_block(current_time, scheduled, reason)
                break  # entrance blocked; retry next step
            self.next_arrival_index += 1

    def _log_block(self, current_time, scheduled, reason):
        """Record one failed admission attempt (capped, aggregated later)."""
        if len(self.admission_blocks) >= self.max_admission_blocks:
            return
        active = [v for v in self.vehicles if v.active]
        front = active[-1] if active else None
        cfg = self.config
        self.admission_blocks.append(
            {
                "t": round(current_time, 2),
                "scheduled_arrival": round(scheduled, 2),
                "waiting_s": round(current_time - scheduled, 2),
                "reason": reason,
                "front_id": None if front is None else front.id,
                "front_position_m": None if front is None else round(front.position, 1),
                "front_speed_mps": None if front is None else round(front.speed, 2),
                "front_time_headway_s": (
                    None if front is None else round(getattr(front, "time_headway", float("nan")), 2)
                ),
                "bottleneck_active": bool(
                    cfg.bottleneck_t_start <= current_time < cfg.bottleneck_t_end
                ),
            }
        )

    def _try_spawn(self, current_time, scheduled):
        """Create one vehicle if the entrance is clear, else return (None, cause).

        Two checks gate the entrance. The first is the teacher's original
        spacing rule. The second (kinematic) is our addition: a new vehicle
        enters at ``initial_speed`` and must at least be able to brake down
        to the front vehicle's speed without overlapping it. The caller logs
        which of the two blocked admission.
        """
        active_vehicles = [vehicle for vehicle in self.vehicles if vehicle.active]
        vehicle_front = active_vehicles[-1] if active_vehicles else None

        # Do not insert a new vehicle on top of a queue at the entrance.
        # (Teacher-original condition.)
        if vehicle_front is not None:
            entry_gap = (
                self.config.vehicle_length
                + self.config.idm_minimum_spacing
                + self.config.initial_speed * self.config.idm_time_headway
            )
            if vehicle_front.position < entry_gap:
                return None, "spacing"

            # Kinematic entry condition (OUR addition, not the teacher's):
            # a new vehicle enters at initial_speed, and even maximum braking
            # cannot avoid overlapping the front vehicle unless the available
            # gap covers the stopping-distance difference
            # (v0^2 - vf^2) / (2 * b_max). Deferring entry until the front
            # vehicle has moved on is the simulation analogue of real-world
            # ramp metering. Without this check, a vehicle spawned behind a
            # slow queue tail is doomed at birth — a flaw we exposed with
            # random arrivals (experiment 2/4). Applied identically to every
            # strategy, so it cannot bias the comparison.
            available_gap = (
                vehicle_front.position
                - self.config.vehicle_length
                - self.config.idm_minimum_spacing
            )
            speed_gap_sq = (
                self.config.initial_speed ** 2 - vehicle_front.speed ** 2
            )
            if speed_gap_sq > 0:
                required_distance = speed_gap_sq / (
                    2.0 * self.config.idm_maximum_deceleration
                )
                if required_distance > available_gap:
                    return None, "kinematic"

        vehicle_id = len(self.vehicles) + 1
        use_llm = False
        if issubclass(self.vehicle_class, LLMVehicle):
            if self.llm_ego_id is not None:
                use_llm = (vehicle_id == self.llm_ego_id)
            elif self.llm_fraction is not None and self.llm_fraction > 0:
                every_n = max(1, round(1.0 / self.llm_fraction))
                use_llm = (vehicle_id % every_n == 0)
            elif self.llm_fraction is None:
                use_llm = True
            # fraction == 0.0 → use_llm stays False (all IDM)

        if not issubclass(self.vehicle_class, LLMVehicle) or not use_llm:
            vehicle = IDMVehicle(self.config, vehicle_id, vehicle_front)
        else:
            # Trace only the tracked ego: a full-fleet LLM run would
            # otherwise keep hundreds of thousands of log entries in memory.
            trace = (
                self.llm_ego_id is not None and vehicle_id == self.llm_ego_id
            )
            vehicle = self.vehicle_class(
                self.config, vehicle_id, vehicle_front,
                llm_client=self.llm_client,
                log_decisions=trace,
                **self.llm_trigger_params,
            )
        vehicle.scheduled_arrival = scheduled
        vehicle.entry_time = current_time
        vehicle.record_state(current_time)
        self.vehicles.append(vehicle)
        self.entry_log.append(
            {
                "id": vehicle_id,
                "scheduled_arrival": round(scheduled, 3),
                "entry_time": round(current_time, 3),
                "entry_delay": round(current_time - scheduled, 3),
            }
        )
        return vehicle, None
