"""
Same logic as data_environments.py, split into self-contained blocks
for blog embedding via pymdownx.snippets.
"""

# --8<-- [start:starting-code-and-tests]
_ORIGINAL_CODE = '''\
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
'''

_TEST_CODE = '''\
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
'''
# --8<-- [end:starting-code-and-tests]

# --8<-- [start:real-verifier]
import os
import subprocess
import sys
import tempfile


def run_pytest(code: str) -> dict:
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
    return {"passed": result.returncode == 0, "output": result.stdout[-1500:]}
# --8<-- [end:real-verifier]

# --8<-- [start:synthesis-prompt]
_SYNTHESIZE_PROMPT_TEMPLATE = (
    "Here is a working Python function:\n\n"
    "```python\n{original_code}```\n\n"
    "Introduce exactly ONE subtle, realistic bug into this function -- the kind a "
    "developer might genuinely introduce by accident (an off-by-one, a wrong comparison "
    "operator, a mishandled edge case). Do not add comments pointing out the bug. "
    "Return ONLY the complete modified function in a python code block."
)
# --8<-- [end:synthesis-prompt]
