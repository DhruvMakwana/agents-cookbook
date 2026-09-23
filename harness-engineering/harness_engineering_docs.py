"""
Same logic as harness_engineering.py, split into self-contained blocks for
blog embedding via pymdownx.snippets.
"""

# --8<-- [start:policy-data]
_POLICIES = {
    ("Nimbus Cloud Storage", "refund_policy"): "Full refund within 14 days of purchase, no questions asked.",
    ("Nimbus Cloud Storage", "data_retention_policy"): "Deleted files are permanently purged after 30 days.",
    ("Pinnacle Backup", "refund_policy"): "Refunds available within 30 days, prorated after the first 7 days.",
    ("Pinnacle Backup", "data_retention_policy"): "Backups are retained indefinitely until the account is closed.",
    ("Vertex Sync", "refund_policy"): "No refunds after the 7-day trial period ends.",
    # Deliberately ambiguous / non-answer -- a real test of self-verification discipline
    ("Vertex Sync", "data_retention_policy"): "Data retention varies by plan tier; contact support for specifics.",
}

_PRODUCTS = ["Nimbus Cloud Storage", "Pinnacle Backup", "Vertex Sync"]
_CRITERIA = ["refund_policy", "data_retention_policy"]


def lookup_policy(product: str, criterion: str) -> dict:
    text = _POLICIES.get((product, criterion))
    return {"policy_text": text} if text else {"error": "not found"}
# --8<-- [end:policy-data]

# --8<-- [start:progress-file]
class ProgressFile:
    """A minimal real progress file / feature checklist, mirroring the documented
    claude-progress.txt + feature-checklist pattern: one entry per (product,
    criterion) pair, each starting unfilled until a session records a real finding."""

    def __init__(self):
        self.items = {
            (p, c): {"finding": None, "status": None}
            for p in _PRODUCTS for c in _CRITERIA
        }

    def update(self, product: str, criterion: str, finding: str, status: str) -> dict:
        key = (product, criterion)
        if key not in self.items:
            return {"error": "unknown checklist item"}
        self.items[key] = {"finding": finding, "status": status}
        return {"ok": True}

    def render(self) -> str:
        lines = []
        for (p, c), v in self.items.items():
            state = v["status"] or "not started"
            lines.append(f"- {p} / {c}: {state}" + (f" -- {v['finding']}" if v["finding"] else ""))
        return "\n".join(lines)

    def remaining(self) -> list:
        return [k for k, v in self.items.items() if v["status"] is None]
# --8<-- [end:progress-file]

# --8<-- [start:session-loop]
def run_session(client, model: str, progress: ProgressFile, system: str, task: str, max_turns: int, tools: list) -> dict:
    messages = [{"role": "user", "content": f"{task}\n\nCurrent progress file:\n{progress.render()}"}]
    calls = []
    for _ in range(max_turns):
        response = client.messages.create(model=model, max_tokens=1500, system=system, tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "max_tokens":
            # A real truncation mid-response -- not a genuine "the agent is done."
            answer = "".join(b.text for b in response.content if b.type == "text")
            return {"answer": answer, "calls": calls, "stopped": "truncated"}
        if response.stop_reason != "tool_use":
            answer = "".join(b.text for b in response.content if b.type == "text")
            return {"answer": answer, "calls": calls, "stopped": "finished"}
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            calls.append({"tool": block.name, "input": block.input})
            if block.name == "lookup_policy":
                result = lookup_policy(**block.input)
            else:
                result = progress.update(**block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})
        messages.append({"role": "user", "content": tool_results})
    return {"answer": "(session turn budget exhausted -- this simulates a context reset)", "calls": calls, "stopped": "budget"}
# --8<-- [end:session-loop]

# --8<-- [start:self-verify-system-prompt]
SELF_VERIFY_SYSTEM = (
    "You are a research assistant filling in a policy-comparison checklist. Use lookup_policy "
    "to find each item's answer, then record it with update_progress_file. Self-verify every "
    "result before recording it: only use status='passing' if the real tool result is a clear, "
    "specific, usable answer to the question. If a result is vague, conditional, or doesn't "
    "actually state the policy (for example, telling you to 'contact support' instead of giving "
    "a real answer), record it with status='needs_follow_up' instead -- do not mark something "
    "passing just because a tool call returned something. Complete the full checklist."
)
# --8<-- [end:self-verify-system-prompt]
