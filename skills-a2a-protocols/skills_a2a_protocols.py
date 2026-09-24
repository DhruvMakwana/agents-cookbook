"""
A real repro of Anthropic's own documented progressive-disclosure claim
for Agent Skills: "until a Skill is triggered, only its name and
description occupy context." Three fictional skills, each with a real,
sized SKILL.md body (level 2) behind a short name+description (level 1).
Two real conditions on the identical task:

  - all_upfront: all three skills' FULL bodies are injected into the
    system prompt on every call, regardless of relevance.
  - progressive: only the three short name+description pairs are in the
    system prompt; a real read_skill tool loads a skill's full body only
    when the agent decides it's actually needed.

Real, measured input_tokens (from the API's own usage field) on the
identical task -- which only needs ONE of the three skills.

Run: python skills_a2a_protocols.py
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"

# ------------------------------------------------------- Three fictional skills

_SKILLS = {
    "pdf-forms": {
        "description": "Fill out and validate PDF form fields programmatically, including checkboxes and signatures.",
        "body": (
            "# PDF Forms Skill\n\n"
            "## When to use\nUse this skill whenever the user needs to fill in, validate, or extract values from a PDF form.\n\n"
            "## Field types\n" + "\n".join(f"- Field type {i}: handling notes and edge cases for form field variant {i}, including validation rules and common encoding pitfalls." for i in range(1, 40)) + "\n\n"
            "## Procedure\n1. Load the PDF.\n2. Enumerate form fields.\n3. Map user-provided values to fields.\n4. Validate required fields.\n5. Flatten and save.\n"
        ),
    },
    "invoice-processing": {
        "description": "Extract line items, totals, and tax details from vendor invoices in various formats.",
        "body": (
            "# Invoice Processing Skill\n\n"
            "## When to use\nUse this skill whenever the user needs to extract structured data from an invoice document.\n\n"
            "## Line item patterns\n" + "\n".join(f"- Vendor format {i}: layout quirks and parsing notes for invoice template variant {i}, including currency and tax placement rules." for i in range(1, 40)) + "\n\n"
            "## Procedure\n1. Identify vendor template.\n2. Extract line items.\n3. Reconcile totals.\n4. Flag discrepancies.\n"
        ),
    },
    "expense-report": {
        "description": "Compile categorized expense reports from a list of receipts, including per-diem and mileage rules.",
        "body": (
            "# Expense Report Skill\n\n"
            "## When to use\nUse this skill whenever the user needs to compile or categorize expenses into a report.\n\n"
            "## Category rules\n" + "\n".join(f"- Category rule {i}: reimbursement policy notes and receipt requirements for expense category variant {i}." for i in range(1, 40)) + "\n\n"
            "## Procedure\n1. Parse receipts.\n2. Categorize.\n3. Apply per-diem/mileage rules.\n4. Total by category.\n"
        ),
    },
}

_TASK = "I have a PDF form for a vendor onboarding application. Walk me through how you'd fill it out correctly -- what's your procedure?"

_READ_SKILL_TOOL = [{
    "name": "read_skill",
    "description": "Load the full instructions for a named skill, only when it's actually relevant to the current task.",
    "input_schema": {"type": "object", "properties": {"skill_name": {"type": "string"}}, "required": ["skill_name"]},
}]


def _all_upfront_system_prompt() -> str:
    parts = ["You have the following skills available, with full instructions inline:\n"]
    for name, skill in _SKILLS.items():
        parts.append(f"\n## Skill: {name}\n{skill['body']}")
    return "".join(parts)


def _progressive_system_prompt() -> str:
    parts = ["You have the following skills available. Use the read_skill tool to load a skill's full instructions only when it's relevant to the current task:\n"]
    for name, skill in _SKILLS.items():
        parts.append(f"- {name}: {skill['description']}\n")
    return "".join(parts)


def _run_all_upfront() -> dict:
    response = client.messages.create(
        model=SONNET, max_tokens=500,
        system=_all_upfront_system_prompt(),
        messages=[{"role": "user", "content": _TASK}],
    )
    return {"input_tokens": response.usage.input_tokens, "skills_loaded": list(_SKILLS.keys())}


def _run_progressive() -> dict:
    messages = [{"role": "user", "content": _TASK}]
    system = _progressive_system_prompt()
    cumulative_input_tokens = 0
    skills_loaded = []

    for _ in range(4):
        response = client.messages.create(model=SONNET, max_tokens=500, system=system, tools=_READ_SKILL_TOOL, messages=messages)
        cumulative_input_tokens += response.usage.input_tokens
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            skill_name = block.input["skill_name"]
            skills_loaded.append(skill_name)
            body = _SKILLS.get(skill_name, {}).get("body", "Error: unknown skill")
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": body})
        messages.append({"role": "user", "content": tool_results})

    return {"cumulative_input_tokens": cumulative_input_tokens, "skills_loaded": skills_loaded}


def progressive_disclosure_demo() -> dict:
    return {"all_upfront": _run_all_upfront(), "progressive": _run_progressive()}


def main() -> None:
    print("=" * 70)
    print("Real repro: Agent Skills progressive disclosure vs. all-upfront loading")
    print("=" * 70)
    print(json.dumps(progressive_disclosure_demo(), indent=2))


if __name__ == "__main__":
    main()
