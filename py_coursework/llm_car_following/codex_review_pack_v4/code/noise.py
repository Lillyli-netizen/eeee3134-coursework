"""Deterministic per-(vehicle, step) pseudo-random values.

The teacher's framework draws all randomness (arrival intervals, bottleneck
influence flags, perception noise) from one global ``random`` stream. That
makes experiments unfair: if a control strategy delays an entry by a few
steps, every subsequent draw shifts, so two strategies no longer face the
same arrival times, the same bottleneck-influence assignment, or the same
perception noise.

This module replaces the global stream with pure functions of
``(seed, vehicle_id, step_index)``: the value for a given vehicle at a given
simulation step is identical no matter which control strategy is running.
Integer-only hashing keeps it platform-independent (no float hashing, no
``random`` module state).
"""

import math

_MASK64 = 0xFFFFFFFFFFFFFFFF


def _hash01(*ints):
    """Mix the given integers and return a float in [0, 1).

    Uses the built-in tuple hash: it runs at C speed (the previous
    hand-rolled integer mixer cost about a third of total runtime, since it
    is called once per vehicle per simulation step) and is deterministic
    for integer tuples — PYTHONHASHSEED only randomises str/bytes hashing.
    """
    h = hash(ints) & _MASK64
    return (h >> 11) / float(1 << 53)


def uniform(seed, vehicle_id, salt=0):
    """Deterministic U[0,1) for one vehicle-level draw (e.g. influence flag)."""
    return _hash01(seed, vehicle_id, salt, 0x51)


def normal(seed, vehicle_id, step_index, salt=0):
    """Deterministic standard normal for one (vehicle, step) draw.

    Box-Muller on two independent hashed uniforms. Used for the IDM
    perception noise so that the noise a vehicle feels at step k is the same
    under every control strategy.
    """
    u1 = max(_hash01(seed, vehicle_id, step_index, salt, 0xA1), 1e-300)
    u2 = _hash01(seed, vehicle_id, step_index, salt, 0xA2)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
