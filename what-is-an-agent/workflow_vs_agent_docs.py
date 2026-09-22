"""
Same logic as workflow_vs_agent.py, split into self-contained blocks with no
cross-function dependencies, for embedding as live snippets in the blog page.
Each function repeats its own small setup rather than importing from a
shared module, so any one block can be copy-pasted and run on its own.
"""

# --8<-- [start:faq_kb]
FAQ = {
    "refund_policy": "Refunds are available within 14 days of purchase for annual plans. Monthly plans are non-refundable.",
    "storage_limits": "The Free tier includes 5GB of storage. The Pro tier includes 2TB of storage.",
    "password_reset": "Reset your password from Settings > Security > Reset Password.",
    "data_export": "You can export all your files as a single ZIP from Settings > Export Data.",
    "account_deletion": "Deleting your account is permanent. Files are removed after a 30-day grace period.",
}
# --8<-- [end:faq_kb]


# --8<-- [start:workflow_pipeline]
def workflow_answer(query: str, faq: dict, generate) -> dict:
    """The fixed pipeline: classify -> retrieve -> generate, no branching.
    Whatever category classify_intent picks, generate_response is stuck with --
    there's no step where the model can say "this isn't right, try something else."
    """
    categories = ", ".join(faq.keys())
    category_raw = generate(
        f"Categories: {categories}\n\nCustomer question: \"{query}\"\n\n"
        "Reply with exactly one category name from the list above. Reply with only the category name."
    ).strip().lower()
    category = next((c for c in faq if c in category_raw), category_raw)

    faq_entry = faq.get(category, "(no matching FAQ entry)")

    answer = generate(
        f"Customer question: \"{query}\"\n\nRelevant FAQ entry: \"{faq_entry}\"\n\n"
        "Write a short, direct reply to the customer using only the FAQ entry above."
    ).strip()

    return {"category": category, "faq_entry": faq_entry, "answer": answer}
# --8<-- [end:workflow_pipeline]


# --8<-- [start:agent_judge_step]
def faq_answers_query(query: str, faq_entry: str, generate) -> bool:
    """The judge step the workflow never has: does the retrieved FAQ actually
    answer this question, or did retrieval just return the closest-sounding entry?
    """
    raw = generate(
        f"Customer question: \"{query}\"\n\nCandidate FAQ entry: \"{faq_entry}\"\n\n"
        "Does this FAQ entry actually answer the customer's question? Reply with only YES or NO."
    ).strip().upper()
    return raw.startswith("Y")
# --8<-- [end:agent_judge_step]


# --8<-- [start:agent_decision_point]
def decide_next_action(query: str, tried_categories: list, faq: dict, generate) -> str:
    """This is the decision point that makes it an agent rather than a workflow:
    the MODEL chooses the next step from live options, based on what just
    happened -- not a fixed `if/else` written into the pipeline code.
    """
    remaining = [c for c in faq if c not in tried_categories]
    raw = generate(
        f"Customer question: \"{query}\"\n\n"
        f"FAQ categories already checked and found NOT to answer this question: {tried_categories}\n"
        f"FAQ categories not yet checked: {remaining}\n\n"
        "Pick exactly one next action: BROADEN (try another FAQ category), "
        "CLARIFY (ask the customer a clarifying question), or ESCALATE (this "
        "needs a human). Reply with only one word: BROADEN, CLARIFY, or ESCALATE."
    ).strip().upper()
    for action in ("BROADEN", "CLARIFY", "ESCALATE"):
        if action in raw:
            return action
    return "ESCALATE"
# --8<-- [end:agent_decision_point]


# --8<-- [start:agent_loop]
def agent_answer(query: str, faq: dict, generate, max_steps: int = 3) -> dict:
    """The full agent loop: retrieve, judge, and if the judge says no, let the
    model itself decide what happens next -- broaden, clarify, or escalate.
    """
    tried_categories = []
    categories = ", ".join(faq.keys())
    category = generate(
        f"Categories: {categories}\n\nCustomer question: \"{query}\"\n\n"
        "Reply with exactly one category name from the list above. Reply with only the category name."
    ).strip().lower()
    category = next((c for c in faq if c in category), category)

    for step in range(1, max_steps + 1):
        faq_entry = faq.get(category, "(no matching FAQ entry)")
        sufficient = faq_answers_query(query, faq_entry, generate)

        if sufficient:
            answer = generate(
                f"Customer question: \"{query}\"\n\nRelevant FAQ entry: \"{faq_entry}\"\n\n"
                "Write a short, direct reply to the customer using only the FAQ entry above."
            ).strip()
            return {"outcome": "answered", "answer": answer, "steps": step}

        tried_categories.append(category)
        action = decide_next_action(query, tried_categories, faq, generate)

        if action == "ESCALATE":
            return {"outcome": "escalated", "answer": "Escalating to a human agent.", "steps": step}
        if action == "CLARIFY":
            return {"outcome": "clarify", "answer": "Could you say more about what you're trying to do?", "steps": step}

        remaining = [c for c in faq if c not in tried_categories]
        category = remaining[0] if remaining else category

    return {"outcome": "budget_exhausted", "answer": "(ran out of steps)", "steps": max_steps}
# --8<-- [end:agent_loop]
