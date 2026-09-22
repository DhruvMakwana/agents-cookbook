"""
Tool design: the same underlying data, exposed to the same model through
three different tool surfaces, measured on real call count and token count --
plus a real comparison of terse versus actionable tool-error messages.

1. Endpoint wrappers: one tool per low-level operation (list, get, filter
   done client-side by the model).
2. Consolidated: fewer, higher-level tools that do composition server-side.
3. Code execution: one tool that runs model-written code against a small
   library, so intermediate data never has to pass through the model's
   context as tokens at all.
4. Errors as observations: the same ambiguous request, sent to a tool with
   a terse validation error and with an actionable one, comparing how many
   turns each takes to reach a valid call.

No framework -- the raw Anthropic client throughout, same as the other
recipes in this cookbook. Run: python tool_design.py
"""

import contextlib
import io
import json
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
HAIKU = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
SONNET = "claude-sonnet-5"


def _call_with_tools(model: str, question: str, tools: list, impls: dict, max_steps: int = 8) -> dict:
    """A plain, unrestricted tool-calling loop -- unlike the ReAct demo in
    reasoning-paradigms, this one lets native parallel tool use happen freely,
    because what's under test here is the tool SURFACE, not the loop shape."""
    messages = [{"role": "user", "content": question}]
    calls = 0
    total_tokens = 0

    for _ in range(max_steps):
        response = client.messages.create(model=model, max_tokens=800, tools=tools, messages=messages)
        calls += 1
        total_tokens += response.usage.input_tokens + response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {"answer": final_text, "calls": calls, "total_tokens": total_tokens}

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = impls[block.name](**block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result) if not isinstance(result, str) else result})
        messages.append({"role": "user", "content": tool_results})

    return {"answer": "(budget exhausted)", "calls": calls, "total_tokens": total_tokens}


# ------------------------------------------------------- Fictional task data

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


def ground_truth_blocked() -> dict:
    return {tid: {"title": t["title"], "reason": t["comments"][-1]} for tid, t in _TASKS.items() if t["status"] == "blocked"}


# --- Surface 1: endpoint wrappers -------------------------------------------

def list_tasks() -> list:
    return [{"id": tid, "title": t["title"], "status": t["status"]} for tid, t in _TASKS.items()]


def list_comments(task_id: str) -> list:
    if task_id not in _TASKS:
        return {"error": f"No task '{task_id}'"}
    return _TASKS[task_id]["comments"]


ENDPOINT_TOOLS = [
    {"name": "list_tasks", "description": "List all tasks with id, title, and status.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "list_comments", "description": "List all comments for a task, oldest first. Example: list_comments(task_id='T-101').",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
]
ENDPOINT_IMPLS = {"list_tasks": lambda: list_tasks(), "list_comments": lambda task_id: list_comments(task_id)}


# --- Surface 2: consolidated -------------------------------------------------

def get_blocked_tasks_with_reasons() -> list:
    return [{"id": tid, "title": t["title"], "latest_comment": t["comments"][-1]} for tid, t in _TASKS.items() if t["status"] == "blocked"]


CONSOLIDATED_TOOLS = [
    {"name": "get_blocked_tasks_with_reasons",
     "description": "Return every currently blocked task, each with its title and its most recent comment (the blocking reason).",
     "input_schema": {"type": "object", "properties": {}}},
]
CONSOLIDATED_IMPLS = {"get_blocked_tasks_with_reasons": lambda: get_blocked_tasks_with_reasons()}


# --- Surface 3: code execution -----------------------------------------------

def execute_python(code: str) -> str:
    """A minimal, non-production sandbox: restricted builtins, only
    list_tasks/list_comments exposed, stdout captured as the tool result.
    Real production code-execution needs process isolation and timeouts --
    this is illustrative of the MECHANISM, not a deployable sandbox."""
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
CODE_EXEC_IMPLS = {"execute_python": lambda code: execute_python(code)}


def tool_surface_demo() -> dict:
    endpoint = _call_with_tools(SONNET, TOOL_QUESTION, ENDPOINT_TOOLS, ENDPOINT_IMPLS)
    consolidated = _call_with_tools(SONNET, TOOL_QUESTION, CONSOLIDATED_TOOLS, CONSOLIDATED_IMPLS)
    code_exec = _call_with_tools(SONNET, TOOL_QUESTION, CODE_EXEC_TOOLS, CODE_EXEC_IMPLS)
    return {"ground_truth": ground_truth_blocked(), "endpoint_wrappers": endpoint, "consolidated": consolidated, "code_execution": code_exec}


# ------------------------------------------------------- Errors as observations

_VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

AMBIGUOUS_REQUEST = (
    "Create a task to fix the login bug, due next Friday, pretty urgent. "
    "You can't ask me follow-up questions right now -- call create_task directly. "
    "For the priority field, pass the user's own words exactly as given ('pretty urgent'); "
    "make your best guess for the date."
)


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


def _create_task_tool(actionable: bool) -> dict:
    return {
        "name": "create_task",
        "description": "Create a new task.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "priority": {"type": "string"}, "due_date": {"type": "string"}},
            "required": ["title", "priority", "due_date"],
        },
    }


def error_message_demo(actionable: bool) -> dict:
    tools = [_create_task_tool(actionable)]
    impls = {"create_task": lambda title, priority, due_date: _validate_create_task(title, priority, due_date, actionable)}
    messages = [{"role": "user", "content": AMBIGUOUS_REQUEST}]
    calls = 0
    attempts = []

    for _ in range(6):
        response = client.messages.create(model=HAIKU, max_tokens=400, tools=tools, messages=messages)
        calls += 1
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {"calls": calls, "attempts": attempts, "succeeded": False, "final_text": final_text}

        for block in response.content:
            if block.type != "tool_use":
                continue
            result = impls[block.name](**block.input)
            attempts.append({"arguments": block.input, "result": result})
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}]})
            if "result" in result:
                return {"calls": calls, "attempts": attempts, "succeeded": True}

    return {"calls": calls, "attempts": attempts, "succeeded": False}


def main() -> None:
    print("=" * 70)
    print("1. TOOL SURFACES: endpoint wrappers vs consolidated vs code execution")
    print("=" * 70)
    print(json.dumps(tool_surface_demo(), indent=2))

    print()
    print("=" * 70)
    print("2. ERRORS AS OBSERVATIONS: terse vs actionable validation errors")
    print("=" * 70)
    print("Terse:", json.dumps(error_message_demo(actionable=False), indent=2))
    print("Actionable:", json.dumps(error_message_demo(actionable=True), indent=2))


if __name__ == "__main__":
    main()
