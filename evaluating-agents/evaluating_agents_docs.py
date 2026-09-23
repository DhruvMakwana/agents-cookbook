"""
Same logic as evaluating_agents.py, split into self-contained blocks with
no cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:outcome_vs_trajectory]
def _text(response, client, model):
    # client.messages.create(...) -- see agent_loop.py for the full call shape.
    ...


_REFERENCE_TOOL = {
    "name": "get_reference_fact",
    "description": "Look up a verified fact from the reference database, given a short topic string.",
    "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
}


def _run_with_optional_tool(question: str, fact_for_this_question: str, client, model) -> dict:
    """One turn: the model may call the reference tool or just answer.
    Returns the final answer and whether the tool was actually called --
    the trajectory, not just the outcome. The tool always returns the one
    fact relevant to this question, regardless of how the model phrases
    the lookup topic -- a fragile exact-string match on the model's own
    topic wording would test string-matching luck, not the mechanism."""
    response = client.messages.create(
        model=model, max_tokens=400, tools=[_REFERENCE_TOOL],
        messages=[{"role": "user", "content": f"Answer this question. You may call get_reference_fact to check the reference database if you need to.\n\n{question}"}],
    )
    tool_called = any(b.type == "tool_use" for b in response.content)
    if tool_called:
        tool_block = next(b for b in response.content if b.type == "tool_use")
        follow_up = client.messages.create(
            model=model, max_tokens=200, tools=[_REFERENCE_TOOL],
            messages=[
                {"role": "user", "content": f"Answer this question. You may call get_reference_fact to check the reference database if you need to.\n\n{question}"},
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_block.id, "content": fact_for_this_question}]},
            ],
        )
        answer = _text(follow_up, client, model)
    else:
        answer = _text(response, client, model)
    return {"question": question, "answer": answer, "tool_called": tool_called}


def outcome_vs_trajectory_demo(client, model) -> dict:
    well_known = _run_with_optional_tool("What is the boiling point of water at sea level, in Celsius?", "100 degrees Celsius", client, model)
    well_known["outcome_correct"] = "100" in well_known["answer"]

    unguessable = _run_with_optional_tool("What year was the Halcyon Reach colony founded?", "2041", client, model)  # fictional, unguessable
    unguessable["outcome_correct"] = "2041" in unguessable["answer"]

    return {"well_known_fact": well_known, "unguessable_fictional_fact": unguessable}
# --8<-- [end:outcome_vs_trajectory]


# --8<-- [start:pass_at_k]
import re

_PROBABILITY_QUESTION = (
    "A committee of 3 people is chosen at random from a group of 5 men and 4 women. "
    "What is the probability that the committee has at least 2 women? Give your final answer "
    "as a simplified fraction, on its own line, in the form: Final answer: a/b"
)
_CORRECT_FRACTION = (17, 42)  # 34/84 simplified


def _check_probability_answer(text: str) -> bool:
    match = re.search(r"Final answer:\s*(\d+)\s*/\s*(\d+)", text)
    if not match:
        return False
    num, den = int(match.group(1)), int(match.group(2))
    return num * _CORRECT_FRACTION[1] == den * _CORRECT_FRACTION[0]


def pass_at_k_demo(client, model, k: int = 5) -> dict:
    """pass@k: did at least one of k independent trials succeed?
    pass^k: did EVERY one of k independent trials succeed? -- the real
    reliability question, since a production agent runs once per real
    request, not k times with a human picking the best try."""
    results = []
    for _ in range(k):
        response = client.messages.create(model=model, max_tokens=500, messages=[{"role": "user", "content": _PROBABILITY_QUESTION}])
        text = _text(response, client, model)
        results.append({"answer": text, "correct": _check_probability_answer(text)})

    successes = sum(1 for r in results if r["correct"])
    pass_at_k = successes >= 1
    pass_hat_k = successes == k
    return {"k": k, "successes": successes, "pass_at_k": pass_at_k, "pass_hat_k": pass_hat_k}
# --8<-- [end:pass_at_k]


# --8<-- [start:capability_vs_regression]
_REGRESSION_SUITE = [
    ("What is 2 + 2?", "4"),
    ("What is 10 * 5?", "50"),
    ("What is 100 / 4?", "25"),
    ("What is 6 squared?", "36"),
]

_BASELINE_SYSTEM = "Answer the arithmetic question directly."
# Motivated by a real, common driver of silent regressions: a formatting
# change made for a genuinely good reason (here, an accessibility-style
# guideline) that a downstream automated grader -- built when answers were
# plain digits -- was never updated to handle.
_CAPABILITY_MOTIVATED_SYSTEM = (
    "Express all numeric answers in words, not digits (e.g. 'forty-two', not '42'), as required "
    "by the new accessibility guideline. This applies to every number in your response, no exceptions."
)


def _run_regression_suite(system: str, client, model) -> list:
    results = []
    for question, expected in _REGRESSION_SUITE:
        response = client.messages.create(model=model, max_tokens=500, system=system, messages=[{"role": "user", "content": question}])
        text = _text(response, client, model)
        passed = expected in text
        results.append({"question": question, "expected": expected, "answer": text, "passed": passed})
    return results


def capability_vs_regression_demo(client, model) -> dict:
    baseline_results = _run_regression_suite(_BASELINE_SYSTEM, client, model)
    new_results = _run_regression_suite(_CAPABILITY_MOTIVATED_SYSTEM, client, model)
    return {
        "baseline": {"results": baseline_results, "all_passed": all(r["passed"] for r in baseline_results)},
        "capability_motivated_change": {"results": new_results, "all_passed": all(r["passed"] for r in new_results)},
    }
# --8<-- [end:capability_vs_regression]
