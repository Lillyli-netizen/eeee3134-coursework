"""Pluggable LLM clients for the two-layer vehicle controller.

The vehicle calls ``decide(observation)`` only on event triggers; each call
must return a *plan* (a target speed and a time headway), not a raw
acceleration. The IDM executor stays responsible for safety between calls.

Clients available:
    - MockLLMClient: deterministic rule policy, validates the whole pipeline
      offline without any API access.
    - QwenLLMClient: calls Alibaba Cloud DashScope (OpenAI-compatible API),
      e.g. qwen-flash / qwen-plus.
"""

import json
import os
import time
import urllib.error
import urllib.request


class LLMClient:
    """Base class: subclasses return a plan dict or None on failure."""

    name = "base"

    def __init__(self):
        self.calls = 0
        self.failures = 0

    def decide(self, observation):
        """Return {"target_speed": m/s, "time_headway": s, "reason": str}
        or None when no usable decision could be produced."""
        raise NotImplementedError


class MockLLMClient(LLMClient):
    """Rule-based stand-in for the LLM planner (offline development).

    It encodes the behaviour we expect a good LLM planner to show:
    anticipate the bottleneck early with a smooth speed ramp, cruise at the
    limit otherwise, and increase the time headway moderately when genuinely
    closing on a leader. Headway bumps stay small: raising the desired time
    headway instantly inflates the IDM desired gap, and an exaggerated bump
    makes a comfortable follower brake hard (positive feedback cascade).
    """

    name = "mock"

    def decide(self, observation):
        self.calls += 1
        limit = observation["current_speed_limit"]
        distance = observation["distance_to_bottleneck_start"]
        inside = observation["inside_bottleneck"]
        active = observation["bottleneck_active"]
        speed = observation["speed"]
        gap = observation["gap"]
        relative_speed = observation["relative_speed"]

        reason = "cruise at limit"

        if inside and active:
            target = limit
            reason = "inside bottleneck, follow zone limit"
        elif active and 0.0 <= distance <= 300.0:
            # Linear anticipation ramp: 30 m/s at 300 m -> 3 m/s at 0 m.
            target = min(limit, 3.0 + 0.09 * distance)
            reason = "anticipate bottleneck, ramp down early"
        else:
            target = limit

        # Moderate headway bump only when actually closing fast AND the
        # gap is already below the T=1.3 desired spacing.
        headway = 1.0
        if (
            gap is not None
            and relative_speed is not None
            and relative_speed > 1.0
            and gap < 2.0 + speed * 1.3
        ):
            headway = 1.3
            reason += "; closing on leader, longer headway"

        return {
            "target_speed": target,
            "time_headway": headway,
            "reason": reason,
        }


class MockNoAnticipationClient(LLMClient):
    """Ablation controller: identical to MockLLMClient but WITHOUT the early
    anticipation ramp.

    It cruises at the speed limit until physically inside the bottleneck,
    then obeys the zone limit, and applies the same conservative headway
    bump. Comparing mock vs mock_noant isolates the effect of *early
    deceleration* (the ramp) from everything else, so the claim "early
    deceleration smooths the shockwave" is tested rather than asserted.
    """

    name = "mock_noant"

    def decide(self, observation):
        self.calls += 1
        limit = observation["current_speed_limit"]
        inside = observation["inside_bottleneck"]
        active = observation["bottleneck_active"]
        speed = observation["speed"]
        gap = observation["gap"]
        relative_speed = observation["relative_speed"]

        if inside and active:
            target = limit
            reason = "inside bottleneck, follow zone limit"
        else:
            # No look-ahead: keep cruising at the limit even when an active
            # bottleneck is close ahead.
            target = limit
            reason = "cruise at limit (no anticipation)"

        headway = 1.0
        if (
            gap is not None
            and relative_speed is not None
            and relative_speed > 1.0
            and gap < 2.0 + speed * 1.3
        ):
            headway = 1.3
            reason += "; closing on leader, longer headway"

        return {
            "target_speed": target,
            "time_headway": headway,
            "reason": reason,
        }


class QwenLLMClient(LLMClient):
    """DashScope OpenAI-compatible chat client (default model: qwen-flash).

    Credentials come from environment variables:
        DASHSCOPE_API_KEY  (required)
        LLM_MODEL          (optional, default qwen-flash)
        LLM_BASE_URL       (optional, default DashScope compatible endpoint)
    """

    name = "qwen"
    PROMPT_VERSION = "v2-tuned-2026-11"  # bump whenever SYSTEM_PROMPT changes

    SYSTEM_PROMPT = (
        "You are the longitudinal speed planner of an autonomous car on a "
        "single-lane road. Each call gives a JSON observation: your speed "
        "(m/s), the speed limit, whether a slow zone (bottleneck, 2 m/s) is "
        "currently active, whether you are inside it, the distance to its "
        "start (negative = already entered) and the distance to its end "
        "(negative = already past it), plus gap and relative speed to the "
        "car ahead (null if there is no leader). Choose a target speed and a "
        "car-following time headway for the next few seconds.\n"
        "Rules:\n"
        "1. Before an active slow zone, keep the speed limit while you are "
        "more than about 200 m from its start; only within the last 200 m "
        "reduce speed smoothly (or earlier if the car ahead is slower).\n"
        "2. Inside the slow zone, keep a low speed matching the traffic.\n"
        "3. Once the slow zone is inactive OR the distance to its end is "
        "negative (you are past it), accelerate smoothly back to the speed "
        "limit. Never stay slow after passing the zone.\n"
        "4. Never exceed the speed limit.\n"
        "5. Keep the time headway between 1.0 and 1.6 seconds; do not jump "
        "to the maximum.\n"
        "Reply with ONLY one JSON object, no other text: "
        '{"target_speed": <number m/s>, "time_headway": <number s>, '
        '"reason": "<max 20 words>"}'
    )

    def __init__(self, model=None, api_key=None, base_url=None, timeout=10.0):
        super().__init__()
        self.model = model or os.environ.get("LLM_MODEL", "qwen-flash")
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        self.base_url = (
            base_url
            or os.environ.get(
                "LLM_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        )
        self.timeout = timeout
        self.calls = 0
        self.failures = 0
        self.total_latency = 0.0

    def _chat(self, system_prompt, observation):
        """Send one chat request; return the parsed JSON object or None."""
        if not self.api_key:
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(observation, ensure_ascii=False),
                },
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.api_key,
            },
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            self.calls += 1
            self.failures += 1
            return None
        self.total_latency += time.perf_counter() - started
        self.calls += 1

        try:
            return json.loads(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            self.failures += 1
            return None

    def decide(self, observation):
        decision = self._chat(self.SYSTEM_PROMPT, observation)
        if decision is None:
            return None
        try:
            return {
                "target_speed": float(decision["target_speed"]),
                "time_headway": float(decision["time_headway"]),
                "reason": str(decision.get("reason", ""))[:120],
            }
        except (KeyError, TypeError, ValueError):
            self.failures += 1
            return None


class QwenAccelClient(QwenLLMClient):
    """Ablation client: the model returns a raw acceleration command.

    Used only by the single-layer LLMDirectVehicle baseline, to show what
    happens when the LLM is allowed to command acceleration directly with
    no IDM safety layer underneath.
    """

    name = "qwen_accel"

    SYSTEM_PROMPT = (
        "You are the direct acceleration controller of an autonomous car on "
        "a single-lane road. Each call gives a JSON observation: your speed "
        "(m/s), the speed limit, whether a slow zone (bottleneck, 2 m/s) is "
        "active, whether you are inside it, distances to its start and end "
        "(negative = already passed), plus gap and relative speed to the car "
        "ahead (null if no leader).\n"
        "Output the acceleration you would apply now, between -8 and +2 "
        "m/s^2. Negative is braking. Avoid collisions and hard braking, and "
        "return to the speed limit after the slow zone.\n"
        "Reply with ONLY one JSON object, no other text: "
        '{"acceleration": <number m/s^2>, "reason": "<max 20 words>"}'
    )

    def decide_acceleration(self, observation):
        decision = self._chat(self.SYSTEM_PROMPT, observation)
        if decision is None:
            return None
        try:
            return {
                "acceleration": float(decision["acceleration"]),
                "reason": str(decision.get("reason", ""))[:120],
            }
        except (KeyError, TypeError, ValueError):
            self.failures += 1
            return None


def build_client(kind, model=None, api_key=None):
    """Factory used by main.py / run_comparison.py."""
    if kind == "mock":
        return MockLLMClient()
    if kind == "mock_noant":
        return MockNoAnticipationClient()
    if kind == "qwen":
        return QwenLLMClient(model=model, api_key=api_key)
    if kind == "qwen_accel":
        return QwenAccelClient(model=model, api_key=api_key)
    raise ValueError("unknown LLM client kind: %s" % kind)
