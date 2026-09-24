"""
Two real repros of SWE-agent's documented Agent-Computer Interface (ACI)
principles: a real syntax-linting guardrail on a multi-step code edit
(reproducing the mechanism behind SWE-agent's own real 18.0% -> 10.3%
SWE-bench Lite ablation, at small scale), and a real review-loop repro --
giving the agent a verifiable check (a real test suite it can actually run)
versus no way to check its own work before submitting.

Run: python coding_agents_mechanisms.py
"""

import ast
import json
import os
import subprocess
import sys
import tempfile

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


# ------------------------------------------------------- Demo 1: syntax-linting guardrail

_TEMPERATURE_SOURCE = '''def classify_reading(temp, humidity):
    if temp < 0:
        return "freezing"
    elif temp < 25:
        if humidity > 80:
            return "cold and damp"
        else:
            return "cold and dry"
    else:
        return "warm"
'''

_LINT_TASK = (
    "Restructure this using str_replace: the temp < 25 branch should ALSO be split by an "
    "additional wind_speed parameter -- add wind_speed as a new function parameter, and within "
    "each of the existing humidity branches, add a nested check: if wind_speed > 20 append ', "
    "windy' to the returned string, else leave it as is. The warm and freezing branches are "
    "unaffected by wind_speed. Make all the edits needed."
)


def _make_edit_tools() -> list:
    return [{
        "name": "str_replace",
        "description": "Replace exact text old_str with new_str in the file. old_str must match verbatim, including whitespace/indentation.",
        "input_schema": {
            "type": "object",
            "properties": {"old_str": {"type": "string"}, "new_str": {"type": "string"}},
            "required": ["old_str", "new_str"],
        },
    }]


def _lint(code: str) -> dict:
    try:
        ast.parse(code)
        return {"valid": True}
    except SyntaxError as e:
        return {"valid": False, "error": f"SyntaxError: {e.msg} at line {e.lineno}"}


def _edit_trial(source: str, task: str, with_lint_guardrail: bool, max_turns: int = 6) -> dict:
    code = source
    tools = _make_edit_tools()
    system = (
        "You are editing a Python file with str_replace. Make the requested changes."
        + (" After each edit, you'll see whether the file is still syntactically valid Python -- fix it if not." if with_lint_guardrail else "")
    )
    messages = [{"role": "user", "content": f"{task}\n\nCurrent file:\n{code}"}]
    edits = 0
    for _ in range(max_turns):
        response = client.messages.create(model=SONNET, max_tokens=1000, system=system, tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            edits += 1
            old, new = block.input["old_str"], block.input["new_str"]
            if old in code:
                code = code.replace(old, new, 1)
                result = {"ok": True}
            else:
                result = {"ok": False, "error": "old_str not found verbatim in the current file"}
            if with_lint_guardrail:
                result["lint"] = _lint(code)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    final_lint = _lint(code)
    return {"final_valid_syntax": final_lint["valid"], "edits_made": edits, "final_code": code}


def linting_guardrail_demo(trials: int = 5) -> dict:
    result = {"no_guardrail": [], "with_guardrail": []}
    for _ in range(trials):
        result["no_guardrail"].append(_edit_trial(_TEMPERATURE_SOURCE, _LINT_TASK, with_lint_guardrail=False))
    for _ in range(trials):
        result["with_guardrail"].append(_edit_trial(_TEMPERATURE_SOURCE, _LINT_TASK, with_lint_guardrail=True))
    result["no_guardrail_valid_rate"] = sum(1 for r in result["no_guardrail"] if r["final_valid_syntax"]) / trials
    result["with_guardrail_valid_rate"] = sum(1 for r in result["with_guardrail"] if r["final_valid_syntax"]) / trials
    return result


# ------------------------------------------------------- Demo 2: review loop / verifiable tasks

_BUGGY_SOURCE = '''def find_first_greater(sorted_list, target):
    lo, hi = 0, len(sorted_list)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_list[mid] <= target:
            lo = mid + 1
        else:
            hi = mid - 1
    return lo
'''

_TEST_SUITE = '''
def test_find_first_greater():
    r1 = find_first_greater([1, 3, 3, 5, 7], 3)
    assert r1 == 3, f"case 1: expected 3, got {r1}"
    r2 = find_first_greater([1, 3, 3, 5, 7], 7)
    assert r2 == 5, f"case 2: expected 5, got {r2}"
    r3 = find_first_greater([], 5)
    assert r3 == 0, f"case 3: expected 0, got {r3}"
    # These two cases are the ones a naive read-through of the code tends to miss --
    # they only surface by actually running the function.
    r4 = find_first_greater([0, 2], 0)
    assert r4 == 1, f"case 4: expected 1, got {r4}"
    r5 = find_first_greater([1, 3, 4, 5, 6, 9, 9], 1)
    assert r5 == 1, f"case 5: expected 1, got {r5}"
    print("ALL TESTS PASSED")

test_find_first_greater()
'''

_BUGFIX_TASK = (
    "The function find_first_greater(sorted_list, target) is supposed to do a binary search "
    "returning the index of the first element strictly greater than target (or len(sorted_list) "
    "if none exists). It has a real bug -- a classic binary-search off-by-one -- that only "
    "breaks correctness for certain inputs. Fix it using str_replace."
)


def _run_real_tests(code: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "solution.py")
        with open(path, "w") as f:
            f.write(code + "\n" + _TEST_SUITE)
        try:
            proc = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            return {"passed": False, "output": "(timed out)"}
        return {"passed": "ALL TESTS PASSED" in proc.stdout, "output": (proc.stdout + proc.stderr).strip()}


def _bugfix_trial(with_review_loop: bool, max_turns: int = 6) -> dict:
    code = _BUGGY_SOURCE
    tools = [{
        "name": "str_replace",
        "description": "Replace exact text old_str with new_str in the file.",
        "input_schema": {"type": "object", "properties": {"old_str": {"type": "string"}, "new_str": {"type": "string"}}, "required": ["old_str", "new_str"]},
    }]
    if with_review_loop:
        tools.append({
            "name": "run_tests",
            "description": "Run the real test suite against the current file and report pass/fail.",
            "input_schema": {"type": "object", "properties": {}},
        })
    system = (
        "You are fixing a bug in a Python file using str_replace."
        + (" You have a run_tests tool -- use it to check your fix actually works before you finish. If tests fail, keep fixing and re-testing." if with_review_loop else " Make your best fix in one edit.")
    )
    messages = [{"role": "user", "content": f"{_BUGFIX_TASK}\n\nCurrent file:\n{code}"}]
    for _ in range(max_turns):
        response = client.messages.create(model=SONNET, max_tokens=1000, system=system, tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "str_replace":
                old, new = block.input["old_str"], block.input["new_str"]
                if old in code:
                    code = code.replace(old, new, 1)
                    result = {"ok": True}
                else:
                    result = {"ok": False, "error": "old_str not found verbatim"}
            else:  # run_tests
                result = _run_real_tests(code)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    return _run_real_tests(code)  # independently verified, not self-reported


def review_loop_demo(trials: int = 5) -> dict:
    result = {"no_review_loop": [], "with_review_loop": []}
    for _ in range(trials):
        result["no_review_loop"].append(_bugfix_trial(with_review_loop=False))
    for _ in range(trials):
        result["with_review_loop"].append(_bugfix_trial(with_review_loop=True))
    result["no_review_loop_pass_rate"] = sum(1 for r in result["no_review_loop"] if r["passed"]) / trials
    result["with_review_loop_pass_rate"] = sum(1 for r in result["with_review_loop"] if r["passed"]) / trials
    return result


def main() -> None:
    print("=" * 70)
    print("DEMO 1: syntax-linting guardrail (reproducing SWE-agent's ACI finding)")
    print("=" * 70)
    print(json.dumps(linting_guardrail_demo(), indent=2))

    print()
    print("=" * 70)
    print("DEMO 2: review loop -- a real, independently-checked test suite in the loop or not")
    print("=" * 70)
    print(json.dumps(review_loop_demo(), indent=2))


if __name__ == "__main__":
    main()
