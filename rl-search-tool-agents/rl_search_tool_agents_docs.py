"""
Same logic as rl_search_tool_agents.py, split into self-contained blocks
for blog embedding via pymdownx.snippets.
"""

# --8<-- [start:reward-functions]
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
# --8<-- [end:reward-functions]

# --8<-- [start:trials]
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
# --8<-- [end:trials]
