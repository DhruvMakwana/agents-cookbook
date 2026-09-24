"""
A real repro of the two mechanisms this topic is built around:

  1. SWE-smith's real task-synthesis approach: "automatically synthesizes
     ...task instances that break existing test(s) in the codebase" --
     generating a task from ARBITRARY working code, not requiring an
     existing real-world PR or issue.

  2. The "verifiers" concept behind RLVR (RL with Verifiable Rewards):
     a real, deterministic check -- actually running the test suite --
     rather than an LLM's judgment, producing a real binary reward.

A real, working Python function with a real, passing test suite. Step
1: a real Claude call introduces a subtle, plausible bug (synthesizing
a task the SWE-smith way -- from working code, not a real historical
bug report). Step 2: the REAL test suite is actually executed against
the buggy code -- a real, deterministic verifier, not an LLM's opinion
about whether the code looks right. Step 3: a second real Claude call
(a "fixing agent"), given only the real failing test output, attempts
a fix. Step 4: the real test suite is run again to verify the fix.

Run: python data_environments.py
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"

# ------------------------------------------------------- Real, working starting code + tests

_ORIGINAL_CODE = textwrap.dedent('''\
    def merge_intervals(intervals):
        """Merge overlapping intervals. Input: list of [start, end] pairs."""
        if not intervals:
            return []
        intervals = sorted(intervals, key=lambda pair: pair[0])
        merged = [intervals[0]]
        for start, end in intervals[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = [last_start, max(last_end, end)]
            else:
                merged.append([start, end])
        return merged
''')

_TEST_CODE = textwrap.dedent('''\
    from solution import merge_intervals

    def test_no_overlap():
        assert merge_intervals([[1, 2], [3, 4]]) == [[1, 2], [3, 4]]

    def test_simple_overlap():
        assert merge_intervals([[1, 3], [2, 6], [8, 10]]) == [[1, 6], [8, 10]]

    def test_touching_intervals():
        assert merge_intervals([[1, 4], [4, 5]]) == [[1, 5]]

    def test_empty():
        assert merge_intervals([]) == []

    def test_unsorted_input():
        assert merge_intervals([[5, 6], [1, 3]]) == [[1, 3], [5, 6]]
''')


def _run_pytest(code: str) -> dict:
    """The real, deterministic verifier -- actually executes the real test suite
    against real code in a fresh temp directory. No LLM judgment involved."""
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "solution.py"), "w") as f:
            f.write(code)
        with open(os.path.join(tmp, "test_solution.py"), "w") as f:
            f.write(_TEST_CODE)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "test_solution.py", "-v", "--tb=short"],
            cwd=tmp, capture_output=True, text=True, timeout=30,
        )
    passed = result.returncode == 0
    return {"passed": passed, "output": result.stdout[-1500:]}


def _extract_code_block(text: str) -> str:
    if "```python" in text:
        return text.split("```python", 1)[1].split("```", 1)[0].strip()
    if "```" in text:
        return text.split("```", 1)[1].split("```", 1)[0].strip()
    return text.strip()


def _response_text(response) -> str:
    """response.content[0] isn't reliably the text block -- a ThinkingBlock can come
    first. Find the actual text block explicitly instead of assuming an index."""
    return "\n".join(b.text for b in response.content if b.type == "text")


def synthesize_buggy_task() -> dict:
    """Step 1+2: a real Claude call introduces a bug into real, working code (SWE-smith's
    task-synthesis approach), then the real test suite verifies the task is genuine --
    i.e. that the tests actually now fail, deterministically."""
    prompt = (
        "Here is a working Python function:\n\n"
        f"```python\n{_ORIGINAL_CODE}```\n\n"
        "Introduce exactly ONE subtle, realistic bug into this function -- the kind a "
        "developer might genuinely introduce by accident (an off-by-one, a wrong comparison "
        "operator, a mishandled edge case). Do not add comments pointing out the bug. "
        "Return ONLY the complete modified function in a python code block."
    )
    response = client.messages.create(model=SONNET, max_tokens=500, messages=[{"role": "user", "content": prompt}])
    buggy_code = _extract_code_block(_response_text(response))
    verification = _run_pytest(buggy_code)
    return {"buggy_code": buggy_code, "tests_genuinely_fail": not verification["passed"], "test_output": verification["output"]}


def fix_and_reverify(buggy_code: str, failing_test_output: str) -> dict:
    """Step 3+4: a second real Claude call, given ONLY the real failing test output (not
    the original correct code), attempts a fix -- then the real test suite verifies it."""
    prompt = (
        "This Python function is failing its test suite:\n\n"
        f"```python\n{buggy_code}```\n\n"
        "Here is the real pytest output:\n\n"
        f"{failing_test_output}\n\n"
        "Fix the bug. Return ONLY the complete corrected function in a python code block."
    )
    response = client.messages.create(model=SONNET, max_tokens=500, messages=[{"role": "user", "content": prompt}])
    fixed_code = _extract_code_block(_response_text(response))
    verification = _run_pytest(fixed_code)
    return {"fixed_code": fixed_code, "all_tests_pass": verification["passed"], "test_output": verification["output"]}


def synthesis_and_verification_demo() -> dict:
    task = synthesize_buggy_task()
    if not task["tests_genuinely_fail"]:
        return {"task_synthesis": task, "fix_attempt": None, "note": "Synthesized task did not genuinely break tests -- no real task to verify a fix against."}
    fix = fix_and_reverify(task["buggy_code"], task["test_output"])
    return {"task_synthesis": task, "fix_attempt": fix}


def main() -> None:
    print("=" * 70)
    print("Real repro: SWE-smith-style task synthesis + real test-based verification")
    print("=" * 70)
    print(json.dumps(synthesis_and_verification_demo(), indent=2))


if __name__ == "__main__":
    main()
