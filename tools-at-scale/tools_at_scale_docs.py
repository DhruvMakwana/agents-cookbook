"""
Same logic as tools_at_scale.py, split into self-contained blocks for
blog embedding via pymdownx.snippets. Each block takes client/model as
parameters instead of relying on module-level globals, so it can be
embedded on its own without the rest of the file.
"""

import contextlib
import io
import json

# --8<-- [start:task]
TASK_QUESTION = (
    "Employee EMP-4471 needs access to DataViz Pro. Look up the employee, check whether a "
    "license seat is available for their department, and provision access if one is."
)
# --8<-- [end:task]

# --8<-- [start:helpdesk-data]
_EMPLOYEES = {"EMP-4471": {"name": "Jamie Cole", "department": "Engineering"}}
_LICENSE_SEATS = {("Engineering", "DataViz Pro"): 12}
_PROVISIONS = {}


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
# --8<-- [end:helpdesk-data]

# --8<-- [start:naive-demo]
def naive_demo(client, model: str, all_tool_specs: list, all_impls: dict) -> dict:
    messages = [{"role": "user", "content": TASK_QUESTION}]
    total_tokens = 0
    calls = 0
    for _ in range(6):
        response = client.messages.create(model=model, max_tokens=500, tools=all_tool_specs, messages=messages)
        calls += 1
        total_tokens += response.usage.input_tokens + response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            answer = "".join(b.text for b in response.content if b.type == "text")
            return {"answer": answer, "calls": calls, "total_tokens": total_tokens}
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = all_impls.get(block.name, lambda **_: {"error": "not implemented"})(**block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    return {"answer": "(budget exhausted)", "calls": calls, "total_tokens": total_tokens}
# --8<-- [end:naive-demo]

# --8<-- [start:tool-search]
_STOPWORDS = {
    "the", "a", "an", "to", "of", "for", "and", "or", "if", "is", "are", "was",
    "were", "be", "been", "being", "their", "them", "it", "its", "this", "that",
    "these", "those", "in", "on", "at", "by", "with", "from", "as", "up", "down",
    "out", "one", "you", "your", "i", "we", "us", "our", "do", "does", "did",
    "has", "have", "had", "will", "would", "should", "can", "could", "may",
    "might", "must", "not", "no", "so", "than", "then", "whether", "who",
    "what", "when", "where", "why", "how", "check", "status",
}

_KEYWORDS_BY_TOOL = {
    "lookup_employee": {"employee", "lookup", "look", "department", "id"},
    "check_license_availability": {"license", "seat", "software", "available"},
    "provision_access": {"provision", "access", "software", "grant"},
}


def _meaningful_words(text: str) -> set:
    raw = text.lower().replace(",", "").replace(".", "").split()
    return {w for w in raw if w not in _STOPWORDS}


def search_relevant_tools(question: str, all_tool_specs: list, top_k: int = 3) -> list:
    """A minimal keyword-overlap retriever -- illustrative of the mechanism
    (pre-filter before the full library ever reaches the model), not a
    production embedding search."""
    words = _meaningful_words(question)
    scored = []
    for tool in all_tool_specs:
        keywords = _KEYWORDS_BY_TOOL.get(tool["name"], _meaningful_words(tool["description"]))
        overlap = len(words & keywords)
        scored.append((overlap, tool))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [tool for _, tool in scored[:top_k]]
# --8<-- [end:tool-search]

# --8<-- [start:programmatic-tool]
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
# --8<-- [end:programmatic-tool]
