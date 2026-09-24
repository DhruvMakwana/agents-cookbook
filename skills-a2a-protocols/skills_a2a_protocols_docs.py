"""
Same logic as skills_a2a_protocols.py, split into self-contained blocks
for blog embedding via pymdownx.snippets.
"""

# --8<-- [start:skills-and-task]
_SKILLS = {
    "pdf-forms": {
        "description": "Fill out and validate PDF form fields programmatically, including checkboxes and signatures.",
        "body": "# PDF Forms Skill\n\n## When to use\n...\n## Procedure\n1. Load the PDF.\n2. Enumerate form fields.\n3. Map user-provided values to fields.\n4. Validate required fields.\n5. Flatten and save.\n",
    },
    "invoice-processing": {
        "description": "Extract line items, totals, and tax details from vendor invoices in various formats.",
        "body": "# Invoice Processing Skill\n\n## When to use\n...\n## Procedure\n1. Identify vendor template.\n2. Extract line items.\n3. Reconcile totals.\n4. Flag discrepancies.\n",
    },
    "expense-report": {
        "description": "Compile categorized expense reports from a list of receipts, including per-diem and mileage rules.",
        "body": "# Expense Report Skill\n\n## When to use\n...\n## Procedure\n1. Parse receipts.\n2. Categorize.\n3. Apply per-diem/mileage rules.\n4. Total by category.\n",
    },
}

_TASK = "I have a PDF form for a vendor onboarding application. Walk me through how you'd fill it out correctly -- what's your procedure?"
# --8<-- [end:skills-and-task]

# --8<-- [start:two-conditions]
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
# --8<-- [end:two-conditions]
