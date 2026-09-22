"""
Same logic as context_engineering.py, split into self-contained blocks with
no cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:poisoning]
def _text(response, client, model):
    # client.messages.create(...) -- see agent_loop.py for the full call shape.
    ...


def poisoning_demo(client, model) -> dict:
    """A hallucinated founding year enters context as a fake tool result.
    Quarantine = the bad turn is caught and replaced before the question
    that depends on it gets asked -- not appended-to-fix, actually removed."""
    system = "You answer questions using only the information provided in this conversation."
    question = "As of 2026, how many years old is Meridian Robotics?"

    poisoned_history = [
        {"role": "user", "content": "Look up when Meridian Robotics was founded."},
        {"role": "assistant", "content": "I'll check the company database."},
        {"role": "user", "content": "[tool_result: company_lookup] Meridian Robotics was founded in 2009."},
        {"role": "assistant", "content": "Meridian Robotics was founded in 2009."},
    ]
    quarantined_history = [
        {"role": "user", "content": "Look up when Meridian Robotics was founded."},
        {"role": "assistant", "content": "I'll check the company database."},
        {"role": "user", "content": "[tool_result: company_lookup, corrected after a data error was caught] Meridian Robotics was founded in 2014."},
        {"role": "assistant", "content": "Meridian Robotics was founded in 2014."},
    ]

    poisoned = _text(client.messages.create(model=model, max_tokens=200, system=system,
                                             messages=poisoned_history + [{"role": "user", "content": question}]), client, model)
    quarantined = _text(client.messages.create(model=model, max_tokens=200, system=system,
                                                messages=quarantined_history + [{"role": "user", "content": question}]), client, model)
    return {"ground_truth_founding_year": 2014, "correct_age_2026": 12, "poisoned_answer": poisoned, "quarantined_answer": quarantined}
# --8<-- [end:poisoning]


# --8<-- [start:distraction]
def distraction_demo(client, model) -> dict:
    """Six prior turns confidently apply a wrong averaging method (divide by
    N-1 instead of N). Compress = drop that flawed history and ask fresh
    instead of carrying it forward."""
    system = "Answer the arithmetic question directly."

    flawed_history = []
    examples = [([2, 4, 6], 6), ([10, 20], 30), ([3, 6, 9], 9), ([6, 6, 6, 6], 8), ([10, 10, 10, 10, 20], 15), ([50, 150], 200)]
    for nums, wrong_avg in examples:
        flawed_history.append({"role": "user", "content": f"What's the average of {', '.join(map(str, nums))}?"})
        flawed_history.append({"role": "assistant", "content": f"The average is {wrong_avg}."})

    question = "What's the average of 10, 20, 30, 40?"
    correct_average = 25  # (10+20+30+40)/4
    pattern_matched_average = 33.33  # what following the demonstrated N-1 pattern would give

    distracted = _text(client.messages.create(model=model, max_tokens=200, system=system,
                                               messages=flawed_history + [{"role": "user", "content": question}]), client, model)
    compressed = _text(client.messages.create(model=model, max_tokens=200, system=system,
                                               messages=[{"role": "user", "content": question}]), client, model)
    return {
        "correct_average": correct_average,
        "pattern_matched_average_if_distracted": pattern_matched_average,
        "distracted_answer": distracted,
        "compressed_answer": compressed,
    }
# --8<-- [end:distraction]


# --8<-- [start:confusion]
import json

_CORRECT_TOOL = {
    "name": "get_live_exchange_rate",
    "description": "Get the current live exchange rate between two currencies.",
    "input_schema": {"type": "object", "properties": {"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": ["from_currency", "to_currency"]},
}
_DECOY_TOOL = {
    "name": "get_exchange_rate_estimate",
    "description": "Provides a quick estimated exchange rate based on last known cached data (may be stale).",
    "input_schema": {"type": "object", "properties": {"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": ["from_currency", "to_currency"]},
}
# Plus 10 more filler tools from unrelated domains (currency symbol lookup,
# crypto prices, unit conversion, stock quotes, ...) -- 12 tools total in
# the confused condition, versus 1 in the clean condition.
_REAL_RATE = 1.08   # EUR -> USD, fictional/illustrative
_STALE_RATE = 1.15  # what the decoy tool returns


def confusion_demo(client, model, filler_tools: list) -> dict:
    question = "How many US dollars is 200 EUR worth, using the live rate?"
    ground_truth = round(200 * _REAL_RATE, 2)
    impls = {"get_live_exchange_rate": lambda **_: {"rate": _REAL_RATE}, "get_exchange_rate_estimate": lambda **_: {"rate": _STALE_RATE}}

    def run(tools):
        messages = [{"role": "user", "content": question}]
        for _ in range(4):
            response = client.messages.create(model=model, max_tokens=300, tools=tools, messages=messages)
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                return {"answer": _text(response, client, model), "tool_called": None}
            block = next(b for b in response.content if b.type == "tool_use")
            result = impls.get(block.name, lambda **_: {"error": "not implemented"})(**block.input)
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}]})
            if block.name in impls:
                final = client.messages.create(model=model, max_tokens=200, tools=tools, messages=messages)
                return {"answer": _text(final, client, model), "tool_called": block.name}
        return {"answer": "(budget exhausted)", "tool_called": None}

    clean = run([_CORRECT_TOOL])
    confused = run([_CORRECT_TOOL, _DECOY_TOOL] + filler_tools)
    return {"ground_truth_usd": ground_truth, "clean_result": clean, "confused_result": confused, "tool_count_confused": 2 + len(filler_tools)}
# --8<-- [end:confusion]


# --8<-- [start:clash]
def clash_demo(client, model) -> dict:
    """Two contradictory refund-window facts in context at once. Fix =
    prune the stale one once a newer, superseding fact is known."""
    system = "You answer questions using only the information provided in this conversation."
    question = "What is the refund window, in days?"

    clashing_history = [
        {"role": "user", "content": "[policy_doc v1, published Jan 2026] The refund window is 30 days."},
        {"role": "user", "content": "[policy_doc v2, published Aug 2026, supersedes v1] The refund window is 14 days."},
    ]
    pruned_history = [
        {"role": "user", "content": "[policy_doc v2, published Aug 2026, current policy] The refund window is 14 days."},
    ]

    clashing = _text(client.messages.create(model=model, max_tokens=200, system=system,
                                             messages=clashing_history + [{"role": "user", "content": question}]), client, model)
    pruned = _text(client.messages.create(model=model, max_tokens=200, system=system,
                                           messages=pruned_history + [{"role": "user", "content": question}]), client, model)
    return {"ground_truth_days": 14, "clashing_answer": clashing, "pruned_answer": pruned}
# --8<-- [end:clash]
