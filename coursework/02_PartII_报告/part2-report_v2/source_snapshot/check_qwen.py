"""Smoke test: verify DashScope (Qwen) credentials with one single call.

Usage:
    python check_qwen.py
"""

import os
import sys

from llm_client import QwenLLMClient

client = QwenLLMClient()

print("model   :", client.model)
print("base_url:", client.base_url)
print("api key :", "SET (len=%d)" % len(client.api_key) if client.api_key else "MISSING")

if not client.api_key:
    print("\nDASHSCOPE_API_KEY 未设置。请先执行 setx 并重开终端/Trae。")
    sys.exit(1)

observation = {
    "vehicle_id": 1,
    "time": 0.0,
    "speed": 30.0,
    "current_speed_limit": 30,
    "bottleneck_active": True,
    "inside_bottleneck": False,
    "distance_to_bottleneck_start": 200.0,
    "gap": 60.0,
    "relative_speed": 0.0,
    "leader_speed": 30.0,
}

decision = client.decide(observation)
if decision is None:
    print("\n调用失败：requests=%d, failures=%d" % (client.calls, client.failures))
    print("请检查 key 是否完整、base_url 是否与业务空间一致、以及账户是否有可用额度。")
    sys.exit(2)

print("\n调用成功：%.2f s" % (client.total_latency / client.calls))
print("target_speed :", decision["target_speed"])
print("time_headway :", decision["time_headway"])
print("reason       :", decision["reason"])
