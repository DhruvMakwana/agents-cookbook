"""
Three real experiments in how agent evals actually work, not just the
vocabulary. No framework -- the raw Anthropic client throughout, same as
the rest of this cookbook.

1. Outcome vs. trajectory grading: does the agent get the right answer by
   actually doing the intended procedure, or by skipping it? Both are
   tested for the same task, real trajectories captured.
2. pass@k vs. pass^k: the same task run k=5 independent times. pass@k asks
   "did it succeed at least once"; pass^k asks "did it succeed every
   time" -- the real reliability question. Real, not simulated, variance.
3. Capability vs. regression suites: a small suite of trivial tasks that
   should never fail, re-run after a system-prompt change made to help a
   different, harder capability task -- checking for a real regression.

Run: python evaluating_agents.py
"""

import json
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
HAIKU = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")


def _call(prompt: str, system: str = None, tools: list = None, max_tokens: int = 400, model: str = HAIKU):
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
    return client.messages.create(**kwargs)


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


# ------------------------------------------------------- 1. Outcome vs. trajectory

_REFERENCE_TOOL = {
    "name": "get_reference_fact",
    "description": "Look up a verified fact from the reference database, given a short topic string.",
    "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
}


def _run_with_optional_tool(question: str, fact_for_this_question: str) -> dict:
    """One turn: the model may call the reference tool or just answer.
    Returns the final answer and whether the tool was actually called --
    the trajectory, not just the outcome. The tool always returns the one
    fact relevant to this question, regardless of how the model phrases
    the lookup topic -- a fragile exact-string match on the model's own
    topic wording would test string-matching luck, not the mechanism."""
    response = _call(
        f"Answer this question. You may call get_reference_fact to check the reference database if you need to.\n\n{question}",
        tools=[_REFERENCE_TOOL],
    )
    tool_called = any(b.type == "tool_use" for b in response.content)
    if tool_called:
        tool_block = next(b for b in response.content if b.type == "tool_use")
        follow_up = client.messages.create(
            model=HAIKU, max_tokens=200, tools=[_REFERENCE_TOOL],
            messages=[
                {"role": "user", "content": f"Answer this question. You may call get_reference_fact to check the reference database if you need to.\n\n{question}"},
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_block.id, "content": fact_for_this_question}]},
            ],
        )
        answer = _text(follow_up)
    else:
        answer = _text(response)
    return {"question": question, "answer": answer, "tool_called": tool_called}


def outcome_vs_trajectory_demo() -> dict:
    well_known = _run_with_optional_tool("What is the boiling point of water at sea level, in Celsius?", "100 degrees Celsius")
    well_known["outcome_correct"] = "100" in well_known["answer"]

    unguessable = _run_with_optional_tool("What year was the Halcyon Reach colony founded?", "2041")  # fictional, unguessable
    unguessable["outcome_correct"] = "2041" in unguessable["answer"]

    return {"well_known_fact": well_known, "unguessable_fictional_fact": unguessable}


# ------------------------------------------------------- 2. pass@k vs. pass^k

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
    # accept either the simplified fraction or an unsimplified equivalent
    return num * _CORRECT_FRACTION[1] == den * _CORRECT_FRACTION[0]


def pass_at_k_demo(k: int = 5) -> dict:
    results = []
    for _ in range(k):
        response = _call(_PROBABILITY_QUESTION, max_tokens=500)
        text = _text(response)
        results.append({"answer": text, "correct": _check_probability_answer(text)})

    successes = sum(1 for r in results if r["correct"])
    pass_at_k = successes >= 1          # at least one success in k trials
    pass_hat_k = successes == k          # every single trial succeeded
    return {"k": k, "successes": successes, "trials": results, "pass_at_k": pass_at_k, "pass_hat_k": pass_hat_k}


# ------------------------------------------------------- 3. Capability vs. regression

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


def _run_regression_suite(system: str) -> list:
    results = []
    for question, expected in _REGRESSION_SUITE:
        response = _call(question, system=system, max_tokens=500)
        text = _text(response)
        passed = expected in text
        results.append({"question": question, "expected": expected, "answer": text, "passed": passed})
    return results


def capability_vs_regression_demo() -> dict:
    baseline_results = _run_regression_suite(_BASELINE_SYSTEM)
    new_results = _run_regression_suite(_CAPABILITY_MOTIVATED_SYSTEM)
    return {
        "baseline": {"results": baseline_results, "all_passed": all(r["passed"] for r in baseline_results)},
        "capability_motivated_change": {"results": new_results, "all_passed": all(r["passed"] for r in new_results)},
    }


def main() -> None:
    print("=" * 70); print("1. OUTCOME vs. TRAJECTORY"); print("=" * 70)
    print(json.dumps(outcome_vs_trajectory_demo(), indent=2))

    print(); print("=" * 70); print("2. PASS@K vs. PASS^K (k=5)"); print("=" * 70)
    print(json.dumps(pass_at_k_demo(), indent=2))

    print(); print("=" * 70); print("3. CAPABILITY vs. REGRESSION SUITE"); print("=" * 70)
    print(json.dumps(capability_vs_regression_demo(), indent=2))


if __name__ == "__main__":
    main()
