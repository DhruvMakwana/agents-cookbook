"""
Same logic as coding_agents_mechanisms.py, split into self-contained
blocks for blog embedding via pymdownx.snippets.
"""

import ast
import os
import subprocess
import sys
import tempfile

# --8<-- [start:lint-guardrail]
def lint(code: str) -> dict:
    try:
        ast.parse(code)
        return {"valid": True}
    except SyntaxError as e:
        return {"valid": False, "error": f"SyntaxError: {e.msg} at line {e.lineno}"}
# --8<-- [end:lint-guardrail]

# --8<-- [start:nested-edit-task]
TEMPERATURE_SOURCE = '''def classify_reading(temp, humidity):
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

LINT_TASK = (
    "Restructure this using str_replace: the temp < 25 branch should ALSO be split by an "
    "additional wind_speed parameter -- add wind_speed as a new function parameter, and within "
    "each of the existing humidity branches, add a nested check: if wind_speed > 20 append ', "
    "windy' to the returned string, else leave it as is. The warm and freezing branches are "
    "unaffected by wind_speed. Make all the edits needed."
)
# --8<-- [end:nested-edit-task]

# --8<-- [start:binary-search-bug]
BUGGY_SOURCE = '''def find_first_greater(sorted_list, target):
    lo, hi = 0, len(sorted_list)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_list[mid] <= target:
            lo = mid + 1
        else:
            hi = mid - 1
    return lo
'''

TEST_SUITE = '''
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

BUGFIX_TASK = (
    "The function find_first_greater(sorted_list, target) is supposed to do a binary search "
    "returning the index of the first element strictly greater than target (or len(sorted_list) "
    "if none exists). It has a real bug -- a classic binary-search off-by-one -- that only "
    "breaks correctness for certain inputs. Fix it using str_replace."
)
# --8<-- [end:binary-search-bug]

# --8<-- [start:real-test-runner]
def run_real_tests(code: str) -> dict:
    """Runs the real test suite in a subprocess, independent of anything the
    agent itself claims -- the agent's own self-report is never trusted."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "solution.py")
        with open(path, "w") as f:
            f.write(code + "\n" + TEST_SUITE)
        try:
            proc = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            return {"passed": False, "output": "(timed out)"}
        return {"passed": "ALL TESTS PASSED" in proc.stdout, "output": (proc.stdout + proc.stderr).strip()}
# --8<-- [end:real-test-runner]
