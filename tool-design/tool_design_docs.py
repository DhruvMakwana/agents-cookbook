"""
Same logic as tool_design.py, split into self-contained blocks with no
cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:tool_surfaces_data]
_TASKS = {
    "T-101": {"title": "Fix login redirect bug", "status": "blocked",
              "comments": ["Reproduced on staging.", "Root cause looks like a stale session cookie.",
                            "Blocked: waiting on infra team to rotate the session-signing key before we can test the fix."]},
    "T-102": {"title": "Add dark mode toggle", "status": "in_progress",
              "comments": ["Design mockups approved.", "Implementing CSS variables now."]},
    "T-103": {"title": "Migrate billing service to new queue", "status": "blocked",
              "comments": ["Queue capacity looks fine.", "Blocked: legal needs to sign off on the new data-retention policy before migration can start."]},
    "T-104": {"title": "Write onboarding docs", "status": "done",
              "comments": ["Draft complete.", "Reviewed and merged."]},
    "T-105": {"title": "Optimize search index rebuild", "status": "in_progress",
              "comments": ["Benchmarked current rebuild time: 40 minutes."]},
    "T-106": {"title": "Deprecate legacy export endpoint", "status": "blocked",
              "comments": ["Usage dropped to near zero.", "Blocked: one internal dashboard still depends on it, waiting for that team to migrate."]},
}

TOOL_QUESTION = "Which tasks are currently blocked, and what's the most recent blocking reason mentioned in their comments? List each task's title and that reason."


def list_tasks() -> list:
    return [{"id": tid, "title": t["title"], "status": t["status"]} for tid, t in _TASKS.items()]


def list_comments(task_id: str) -> list:
    if task_id not in _TASKS:
        return {"error": f"No task '{task_id}'"}
    return _TASKS[task_id]["comments"]
# --8<-- [end:tool_surfaces_data]


# --8<-- [start:endpoint_wrappers]
ENDPOINT_TOOLS = [
    {"name": "list_tasks", "description": "List all tasks with id, title, and status.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "list_comments", "description": "List all comments for a task, oldest first. Example: list_comments(task_id='T-101').",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
]
# Model must: list all tasks, notice which are blocked, then call
# list_comments separately for each blocked one -- every intermediate
# result (including the 3 non-blocked tasks' data) passes through context.
# --8<-- [end:endpoint_wrappers]


# --8<-- [start:consolidated]
def get_blocked_tasks_with_reasons() -> list:
    return [{"id": tid, "title": t["title"], "latest_comment": t["comments"][-1]} for tid, t in _TASKS.items() if t["status"] == "blocked"]


CONSOLIDATED_TOOLS = [
    {"name": "get_blocked_tasks_with_reasons",
     "description": "Return every currently blocked task, each with its title and its most recent comment (the blocking reason).",
     "input_schema": {"type": "object", "properties": {}}},
]
# One purpose-built tool does the filtering server-side -- the model never
# sees the non-blocked tasks or any comment except the one it needs.
# --8<-- [end:consolidated]


# --8<-- [start:code_execution]
import contextlib
import io


def execute_python(code: str) -> str:
    """A minimal, non-production sandbox: restricted builtins, only
    list_tasks/list_comments exposed, stdout captured as the tool result.
    Real production code-execution needs process isolation and timeouts --
    this is illustrative of the mechanism, not a deployable sandbox."""
    safe_globals = {"__builtins__": {"len": len, "range": range, "print": print, "sorted": sorted, "enumerate": enumerate}}
    safe_locals = {"list_tasks": list_tasks, "list_comments": list_comments}
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            exec(code, safe_globals, safe_locals)
    except Exception as e:
        return f"Error executing code: {e}"
    return buffer.getvalue() or "(no output -- did you print the result?)"


CODE_EXEC_TOOLS = [
    {"name": "execute_python",
     "description": (
         "Run Python code against a small library: list_tasks() -> [{id, title, status}], "
         "list_comments(task_id) -> [str, ...] (oldest first). Print whatever you need as the "
         "final result -- only what you print is returned to you, so filter and summarize in code "
         "rather than printing raw data."
     ),
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
]
# The model writes the filtering logic itself; raw comment text for
# non-blocked tasks never has to become tokens in its context at all.
# --8<-- [end:code_execution]


# --8<-- [start:errors_as_observations]
import re

_VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_create_task(title: str, priority: str, due_date: str, actionable: bool) -> dict:
    if priority not in _VALID_PRIORITIES:
        if actionable:
            return {"error": f"Invalid priority '{priority}'. Must be exactly one of: low, medium, high, urgent."}
        return {"error": "ValidationError: priority"}
    if not _DATE_RE.match(due_date):
        if actionable:
            return {"error": f"Invalid due_date '{due_date}'. Must be in YYYY-MM-DD format, e.g. 2026-10-02."}
        return {"error": "ValidationError: due_date"}
    return {"result": f"Created task '{title}' (priority={priority}, due={due_date})"}


# Two conditions, same tool, same request -- only the validation error's
# wording changes. The terse version names what field is wrong; the
# actionable version also states the valid values or the expected format.
# --8<-- [end:errors_as_observations]
