"""
The same 3-step, real-tool-dependent task, answered against a ~25-tool
library three ways: naively (every tool definition in context, one call
per turn), with tool search (pre-filtering to only relevant tools before
the model ever sees the rest), and with programmatic tool calling (the
model writes one program that calls all three real tools and returns only
the final result, executed once).

Run: python tools_at_scale.py
"""

import contextlib
import io
import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


# ------------------------------------------------------- Fictional helpdesk data

_EMPLOYEES = {"EMP-4471": {"name": "Jamie Cole", "department": "Engineering"}}
_LICENSE_SEATS = {("Engineering", "DataViz Pro"): 12}
_PROVISIONS = {}

TASK_QUESTION = (
    "Employee EMP-4471 needs access to DataViz Pro. Look up the employee, check whether a "
    "license seat is available for their department, and provision access if one is."
)


def lookup_employee(employee_id: str) -> dict:
    return _EMPLOYEES.get(employee_id, {"error": "not found"})


def check_license_availability(software: str, department: str) -> dict:
    seats = _LICENSE_SEATS.get((department, software))
    return {"available_seats": seats} if seats is not None else {"available_seats": 0}


def provision_access(employee_id: str, software: str) -> dict:
    key = (employee_id, software)
    if key in _PROVISIONS:
        return {"status": "already provisioned (idempotent replay)", "confirmation_id": _PROVISIONS[key]}
    confirmation_id = f"prov_{employee_id}_{software.replace(' ', '')}"
    _PROVISIONS[key] = confirmation_id
    return {"status": "provisioned", "confirmation_id": confirmation_id}


_REAL_TOOLS = {
    "lookup_employee": {
        "name": "lookup_employee", "description": "Look up an employee's name and department by employee ID.",
        "input_schema": {"type": "object", "properties": {"employee_id": {"type": "string"}}, "required": ["employee_id"]},
        "impl": lambda employee_id: lookup_employee(employee_id),
    },
    "check_license_availability": {
        "name": "check_license_availability", "description": "Check how many license seats are available for a software product in a department.",
        "input_schema": {"type": "object", "properties": {"software": {"type": "string"}, "department": {"type": "string"}}, "required": ["software", "department"]},
        "impl": lambda software, department: check_license_availability(software, department),
    },
    "provision_access": {
        "name": "provision_access", "description": "Provision software access for an employee.",
        "input_schema": {"type": "object", "properties": {"employee_id": {"type": "string"}, "software": {"type": "string"}}, "required": ["employee_id", "software"]},
        "impl": lambda employee_id, software: provision_access(employee_id, software),
    },
}

# ~22 unrelated helpdesk-adjacent filler tools, for scale -- illustrative of
# a real, larger internal tool library, not part of this task's real path.
_FILLER_TOOLS = [
    {"name": n, "description": d, "input_schema": {"type": "object", "properties": {}}}
    for n, d in [
        ("reset_password", "Reset an employee's account password."),
        ("check_ticket_status", "Check the status of a support ticket."),
        ("order_hardware", "Order a hardware item for an employee."),
        ("book_conference_room", "Reserve a conference room."),
        ("report_outage", "Report a system or network outage."),
        ("request_vpn_access", "Request VPN access for remote work."),
        ("check_disk_quota", "Check an employee's storage quota usage."),
        ("archive_mailbox", "Archive an employee's old mailbox."),
        ("update_org_chart", "Update an employee's position in the org chart."),
        ("check_printer_status", "Check whether a printer is online."),
        ("request_parking_pass", "Request a parking pass for an employee."),
        ("schedule_maintenance", "Schedule IT maintenance for a device."),
        ("check_badge_access", "Check an employee's building badge access level."),
        ("submit_expense_report", "Submit an expense report for reimbursement."),
        ("request_loaner_laptop", "Request a temporary loaner laptop."),
        ("check_software_version", "Check the installed version of a software product."),
        ("flag_security_incident", "Flag a potential security incident for review."),
        ("update_emergency_contact", "Update an employee's emergency contact info."),
        ("check_onboarding_status", "Check a new hire's onboarding checklist status."),
        ("request_ergonomic_review", "Request an ergonomic workstation review."),
        ("check_meeting_room_av", "Check AV equipment status in a meeting room."),
        ("submit_facilities_request", "Submit a general facilities request."),
    ]
]

ALL_TOOL_SPECS = [{"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]} for t in _REAL_TOOLS.values()] + _FILLER_TOOLS
ALL_IMPLS = {name: t["impl"] for name, t in _REAL_TOOLS.items()}


# ------------------------------------------------------- Condition A: naive (all tools, one call per turn)

def naive_demo() -> dict:
    messages = [{"role": "user", "content": TASK_QUESTION}]
    total_tokens = 0
    calls = 0
    for _ in range(6):
        response = client.messages.create(model=SONNET, max_tokens=500, tools=ALL_TOOL_SPECS, messages=messages)
        calls += 1
        total_tokens += response.usage.input_tokens + response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return {"answer": _text(response), "calls": calls, "total_tokens": total_tokens}
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = ALL_IMPLS.get(block.name, lambda **_: {"error": "not implemented"})(**block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    return {"answer": "(budget exhausted)", "calls": calls, "total_tokens": total_tokens}


# ------------------------------------------------------- Condition B: tool search (pre-filter, then run)

_KEYWORDS_BY_TOOL = {
    "lookup_employee": {"employee", "lookup", "look", "department", "id"},
    "check_license_availability": {"license", "seat", "software", "available"},
    "provision_access": {"provision", "access", "software", "grant"},
}

# Common words that appear across many unrelated tool descriptions ("check",
# "status", "employee") and would otherwise inflate overlap scores for tools
# that have nothing to do with the actual task -- filtered from both sides
# before scoring.
_STOPWORDS = {
    "the", "a", "an", "to", "of", "for", "and", "or", "if", "is", "are", "was",
    "were", "be", "been", "being", "their", "them", "it", "its", "this", "that",
    "these", "those", "in", "on", "at", "by", "with", "from", "as", "up", "down",
    "out", "one", "you", "your", "i", "we", "us", "our", "do", "does", "did",
    "has", "have", "had", "will", "would", "should", "can", "could", "may",
    "might", "must", "not", "no", "so", "than", "then", "whether", "who",
    "what", "when", "where", "why", "how", "check", "status",
}


def _meaningful_words(text: str) -> set:
    raw = text.lower().replace(",", "").replace(".", "").split()
    return {w for w in raw if w not in _STOPWORDS}


def search_relevant_tools(question: str, top_k: int = 3) -> list:
    """A minimal keyword-overlap retriever -- illustrative of the mechanism
    (pre-filter before the full library ever reaches the model), not a
    production embedding search."""
    words = _meaningful_words(question)
    scored = []
    for tool in ALL_TOOL_SPECS:
        keywords = _KEYWORDS_BY_TOOL.get(tool["name"], _meaningful_words(tool["description"]))
        overlap = len(words & keywords)
        scored.append((overlap, tool))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [tool for _, tool in scored[:top_k]]


def tool_search_demo() -> dict:
    filtered_tools = search_relevant_tools(TASK_QUESTION)
    messages = [{"role": "user", "content": TASK_QUESTION}]
    total_tokens = 0
    calls = 0
    for _ in range(6):
        response = client.messages.create(model=SONNET, max_tokens=500, tools=filtered_tools, messages=messages)
        calls += 1
        total_tokens += response.usage.input_tokens + response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return {"answer": _text(response), "calls": calls, "total_tokens": total_tokens, "filtered_to": [t["name"] for t in filtered_tools]}
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = ALL_IMPLS.get(block.name, lambda **_: {"error": "not implemented"})(**block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    return {"answer": "(budget exhausted)", "calls": calls, "total_tokens": total_tokens}


# ------------------------------------------------------- Condition C: programmatic tool calling

_EXECUTE_WORKFLOW_TOOL = {
    "name": "execute_workflow",
    "description": (
        "Run Python code against a small library: lookup_employee(employee_id) -> dict, "
        "check_license_availability(software, department) -> dict, provision_access(employee_id, software) -> dict. "
        "Write code that calls whichever of these you need, in order, and print only the final result you want "
        "returned -- intermediate results stay in the execution environment unless you print them."
    ),
    "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
}


def execute_workflow(code: str) -> str:
    safe_globals = {"__builtins__": {"print": print, "len": len, "str": str}}
    safe_locals = {
        "lookup_employee": lookup_employee,
        "check_license_availability": check_license_availability,
        "provision_access": provision_access,
    }
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            exec(code, safe_globals, safe_locals)
    except Exception as e:
        return f"Error executing code: {e}"
    return buffer.getvalue() or "(no output -- did you print the result?)"


def programmatic_demo() -> dict:
    messages = [{"role": "user", "content": TASK_QUESTION}]
    total_tokens = 0
    calls = 0
    for _ in range(4):
        response = client.messages.create(model=SONNET, max_tokens=800, tools=[_EXECUTE_WORKFLOW_TOOL], messages=messages)
        calls += 1
        total_tokens += response.usage.input_tokens + response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return {"answer": _text(response), "calls": calls, "total_tokens": total_tokens}
        block = next(b for b in response.content if b.type == "tool_use")
        result = execute_workflow(block.input["code"])
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": block.id, "content": result}]})
    return {"answer": "(budget exhausted)", "calls": calls, "total_tokens": total_tokens}


def main() -> None:
    print("=" * 70); print(f"TOOL LIBRARY SIZE: {len(ALL_TOOL_SPECS)} tools"); print("=" * 70)

    print(); print("A. NAIVE (all tools in context, one call per turn)"); print("-" * 70)
    print(json.dumps(naive_demo(), indent=2))

    _PROVISIONS.clear()
    print(); print("B. TOOL SEARCH (pre-filtered to relevant tools)"); print("-" * 70)
    print(json.dumps(tool_search_demo(), indent=2))

    _PROVISIONS.clear()
    print(); print("C. PROGRAMMATIC TOOL CALLING (one workflow call)"); print("-" * 70)
    print(json.dumps(programmatic_demo(), indent=2))


if __name__ == "__main__":
    main()
