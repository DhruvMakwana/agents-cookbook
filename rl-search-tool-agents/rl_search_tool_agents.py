"""
A real repro of ToolRL's central, verified claim about reward design for
tool-use RL (arXiv 2504.13958): "coarse-grained reward signals, such as
answer matching, fail to offer the finegrained feedback required for
effective learning." This recipe can't run actual RL training (that needs
GPU-hours this cookbook doesn't have) -- what it CAN do, honestly, is
compute both reward styles over real Claude tool-call completions and show
the real, concrete difference in what each reward signal is able to see.

Two reward functions, applied to the same real tool calls:
  - binary: 1.0 if the ENTIRE call (tool name + every parameter) exactly
    matches the expected call, else 0.0 -- the "answer matching" ToolRL
    critiques.
  - fine_grained: ToolRL's own three-component decomposition -- tool name
    match, parameter-name-set match, and parameter-value match -- each
    scored and averaged, so a call that's close gets partial credit.

Run: python rl_search_tool_agents.py
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
HAIKU = "claude-haiku-4-5"

# ------------------------------------------------------- Reward functions under test

def binary_reward(call: dict, expected: dict) -> float:
    """The coarse, 'answer matching' reward ToolRL's abstract names as the failure case."""
    return 1.0 if call == expected else 0.0


def fine_grained_reward(call: dict, expected: dict) -> dict:
    """ToolRL's own three-component decomposition: tool name, parameter names,
    parameter values -- each scored separately, then averaged."""
    tool_name_score = 1.0 if call.get("tool") == expected.get("tool") else 0.0

    expected_params = expected.get("params", {})
    call_params = call.get("params", {})
    expected_keys, call_keys = set(expected_params), set(call_params)
    param_name_score = (
        len(expected_keys & call_keys) / len(expected_keys) if expected_keys else 1.0
    )

    if expected_keys:
        value_matches = sum(1 for k in expected_keys if call_params.get(k) == expected_params.get(k))
        param_value_score = value_matches / len(expected_keys)
    else:
        param_value_score = 1.0

    total = round((tool_name_score + param_name_score + param_value_score) / 3, 4)
    return {
        "tool_name_score": tool_name_score,
        "param_name_score": round(param_name_score, 4),
        "param_value_score": round(param_value_score, 4),
        "total": total,
    }


# ------------------------------------------------------- Real tool-calling trials

_TOOLS = [
    {
        "name": "create_calendar_event",
        "description": "Create a calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "duration_minutes": {"type": "integer"},
            },
            "required": ["title", "date", "duration_minutes"],
        },
    },
    {
        "name": "create_reminder",
        "description": "Create a simple reminder with no duration or scheduling.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}, "date": {"type": "string"}},
            "required": ["text", "date"],
        },
    },
]

_TRIALS = [
    {
        "label": "fully_specified",
        "prompt": "Create a calendar event: title 'Team Sync', date 2026-10-05, duration 30 minutes.",
        "expected": {"tool": "create_calendar_event", "params": {"title": "Team Sync", "date": "2026-10-05", "duration_minutes": 30}},
    },
    {
        "label": "vague_duration",
        "prompt": "Create a calendar event titled 'Team Sync' on 2026-10-05. Keep it brief, like a quick check-in.",
        "expected": {"tool": "create_calendar_event", "params": {"title": "Team Sync", "date": "2026-10-05", "duration_minutes": 30}},
    },
    {
        "label": "decoy_tool_available",
        "prompt": "Remind me about Team Sync on 2026-10-05.",
        "expected": {"tool": "create_calendar_event", "params": {"title": "Team Sync", "date": "2026-10-05", "duration_minutes": 30}},
    },
    {
        "label": "paraphrased_duration",
        "prompt": "Set up a 'Team Sync' meeting for 2026-10-05, half an hour long.",
        "expected": {"tool": "create_calendar_event", "params": {"title": "Team Sync", "date": "2026-10-05", "duration_minutes": 30}},
    },
]


def _get_real_tool_call(prompt: str) -> dict:
    response = client.messages.create(
        model=HAIKU, max_tokens=300, tools=_TOOLS, tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )
    block = next(b for b in response.content if b.type == "tool_use")
    return {"tool": block.name, "params": block.input}


def reward_granularity_demo() -> list:
    results = []
    for trial in _TRIALS:
        call = _get_real_tool_call(trial["prompt"])
        results.append({
            "label": trial["label"],
            "prompt": trial["prompt"],
            "expected": trial["expected"],
            "actual_call": call,
            "binary_reward": binary_reward(call, trial["expected"]),
            "fine_grained_reward": fine_grained_reward(call, trial["expected"]),
        })
    return results


def main() -> None:
    print("=" * 70)
    print("ToolRL repro: binary vs. fine-grained reward on real tool calls")
    print("=" * 70)
    print(json.dumps(reward_granularity_demo(), indent=2))


if __name__ == "__main__":
    main()
