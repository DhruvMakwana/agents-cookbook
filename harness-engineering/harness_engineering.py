"""
Two real repros of Anthropic's own documented harness pattern for
long-running agents (init script + progress file + git commit; self-verify
before marking a checklist item "passing"): a genuine multi-session
continuation across separate, budget-limited conversations that only share
a progress file, and a self-verification discipline test against a
deliberately ambiguous real tool result.

Run: python harness_engineering.py
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


# ------------------------------------------------------- Fictional product-policy data

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


_TOOLS = [
    {
        "name": "lookup_policy",
        "description": "Look up a specific policy for a specific product.",
        "input_schema": {
            "type": "object",
            "properties": {"product": {"type": "string"}, "criterion": {"type": "string", "enum": _CRITERIA}},
            "required": ["product", "criterion"],
        },
    },
    {
        "name": "update_progress_file",
        "description": "Record a checklist item's finding. status must be 'passing' (a clear, usable answer was found) or 'needs_follow_up' (the result was ambiguous, incomplete, or didn't actually answer the question).",
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {"type": "string"},
                "criterion": {"type": "string", "enum": _CRITERIA},
                "finding": {"type": "string"},
                "status": {"type": "string", "enum": ["passing", "needs_follow_up"]},
            },
            "required": ["product", "criterion", "finding", "status"],
        },
    },
]


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


def _run_session(progress: ProgressFile, system: str, task: str, max_turns: int) -> dict:
    messages = [{"role": "user", "content": f"{task}\n\nCurrent progress file:\n{progress.render()}"}]
    calls = []
    for _ in range(max_turns):
        response = client.messages.create(model=SONNET, max_tokens=1500, system=system, tools=_TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "max_tokens":
            # A real truncation mid-response -- not a genuine "the agent is done."
            return {"answer": _text(response), "calls": calls, "stopped": "truncated"}
        if response.stop_reason != "tool_use":
            return {"answer": _text(response), "calls": calls, "stopped": "finished"}
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            calls.append({"tool": block.name, "input": block.input})
            if block.name == "lookup_policy":
                result = lookup_policy(**block.input)
            else:
                result = progress.update(**block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    return {"answer": "(session turn budget exhausted -- this simulates a context reset)", "calls": calls, "stopped": "budget"}


# ------------------------------------------------------- Demo 1: multi-session continuation via progress file

_CONTINUATION_SYSTEM = (
    "You are a research assistant filling in a policy-comparison checklist. ALWAYS check the "
    "current progress file first -- do not re-look-up or re-record anything already marked "
    "passing or needs_follow_up. Use lookup_policy to find each item's real answer, then "
    "record it with update_progress_file. Work through the checklist until it's complete or "
    "you run out of turns."
)


def multi_session_continuation_demo() -> dict:
    progress = ProgressFile()
    task = "Fill in the policy-comparison checklist for all three products across both criteria."

    session_1 = _run_session(progress, _CONTINUATION_SYSTEM, task, max_turns=1)
    after_session_1 = {"remaining": len(progress.remaining()), "checklist": progress.render()}

    session_2 = _run_session(progress, _CONTINUATION_SYSTEM, task, max_turns=5)
    after_session_2 = {"remaining": len(progress.remaining()), "checklist": progress.render()}

    return {
        "session_1": {"stopped": session_1["stopped"], "calls": session_1["calls"]},
        "after_session_1": after_session_1,
        "session_2": {"stopped": session_2["stopped"], "calls": session_2["calls"]},
        "after_session_2": after_session_2,
    }


# ------------------------------------------------------- Demo 2: self-verification discipline

_NO_VERIFY_SYSTEM = (
    "You are a research assistant filling in a policy-comparison checklist. Use lookup_policy "
    "to find each item's answer, then record it with update_progress_file. Complete the full "
    "checklist for all three products and both criteria."
)

_SELF_VERIFY_SYSTEM = (
    "You are a research assistant filling in a policy-comparison checklist. Use lookup_policy "
    "to find each item's answer, then record it with update_progress_file. Self-verify every "
    "result before recording it: only use status='passing' if the real tool result is a clear, "
    "specific, usable answer to the question. If a result is vague, conditional, or doesn't "
    "actually state the policy (for example, telling you to 'contact support' instead of giving "
    "a real answer), record it with status='needs_follow_up' instead -- do not mark something "
    "passing just because a tool call returned something. Complete the full checklist."
)


def self_verification_demo() -> dict:
    result = {}
    task = "Fill in the policy-comparison checklist for all three products across both criteria."
    for label, system in [("no_verify_instruction", _NO_VERIFY_SYSTEM), ("self_verify_instruction", _SELF_VERIFY_SYSTEM)]:
        progress = ProgressFile()
        _run_session(progress, system, task, max_turns=10)
        ambiguous_item = progress.items[("Vertex Sync", "data_retention_policy")]
        result[label] = {"full_checklist": progress.render(), "ambiguous_item_status": ambiguous_item["status"]}
    return result


def main() -> None:
    print("=" * 70)
    print("DEMO 1: multi-session continuation via progress file (a real context reset)")
    print("=" * 70)
    print(json.dumps(multi_session_continuation_demo(), indent=2))

    print()
    print("=" * 70)
    print("DEMO 2: self-verification discipline against a deliberately ambiguous result")
    print("=" * 70)
    print(json.dumps(self_verification_demo(), indent=2))


if __name__ == "__main__":
    main()
