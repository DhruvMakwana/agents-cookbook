"""
Workflow vs. agent: the same customer-support task built two ways, to make
the "decision point" distinction concrete instead of definitional.

Workflow (fixed pipeline, no branching decided by the model):
    classify_intent -> retrieve_faq -> generate_response
    Whatever retrieve_faq returns is what generate_response uses, even if
    it's the wrong FAQ entry for the question.

Agent (a loop with a real decision point):
    classify_intent -> retrieve_faq -> JUDGE whether the FAQ actually
    answers the question -> if not, the MODEL decides its own next action
    (broaden the search, ask a clarifying question, or escalate to a human)
    -> repeat, capped at a hard step budget.

Run: python workflow_vs_agent.py
"""

import json
import os

from dotenv import load_dotenv

from llm import generate

load_dotenv()

# A small, deliberately narrow FAQ knowledge base for a fictional product.
FAQ = {
    "refund_policy": "Refunds are available within 14 days of purchase for annual plans. Monthly plans are non-refundable.",
    "storage_limits": "The Free tier includes 5GB of storage. The Pro tier includes 2TB of storage.",
    "password_reset": "Reset your password from Settings > Security > Reset Password.",
    "data_export": "You can export all your files as a single ZIP from Settings > Export Data.",
    "account_deletion": "Deleting your account is permanent. Files are removed after a 30-day grace period.",
}

MAX_AGENT_STEPS = 3


def classify_intent(query: str) -> str:
    """Ask the model to map a free-form query onto one of the fixed FAQ categories."""
    categories = ", ".join(FAQ.keys())
    prompt = (
        f"Categories: {categories}\n\n"
        f'Customer question: "{query}"\n\n'
        "Reply with exactly one category name from the list above that best matches "
        "this question. Reply with only the category name, nothing else."
    )
    raw = generate(prompt).strip().lower()
    # A small local model sometimes wraps the answer in a sentence or quotes --
    # take the first category name that actually appears in the reply.
    for cat in FAQ:
        if cat in raw:
            return cat
    return raw  # honest fallback: return whatever it said, even if invalid


def retrieve_faq(category: str) -> str:
    return FAQ.get(category, "(no matching FAQ entry)")


def generate_response(query: str, faq_entry: str) -> str:
    prompt = (
        f'Customer question: "{query}"\n\n'
        f'Relevant FAQ entry: "{faq_entry}"\n\n'
        "Write a short, direct reply to the customer using only the FAQ entry above."
    )
    return generate(prompt).strip()


def workflow_answer(query: str) -> dict:
    """The fixed pipeline: no step can change what the next step does."""
    category = classify_intent(query)
    faq_entry = retrieve_faq(category)
    answer = generate_response(query, faq_entry)
    return {"category": category, "faq_entry": faq_entry, "answer": answer, "steps": 1}


def faq_answers_query(query: str, faq_entry: str) -> bool:
    """The judge step: does the retrieved FAQ actually answer this question?"""
    prompt = (
        f'Customer question: "{query}"\n\n'
        f'Candidate FAQ entry: "{faq_entry}"\n\n'
        "Does this FAQ entry actually answer the customer's question? "
        "Reply with only YES or NO."
    )
    raw = generate(prompt).strip().upper()
    return raw.startswith("Y")


def decide_next_action(query: str, tried_categories: list[str]) -> str:
    """The decision point: the MODEL picks the next action, not fixed code."""
    remaining = [c for c in FAQ if c not in tried_categories]
    prompt = (
        f'Customer question: "{query}"\n\n'
        f"FAQ categories already checked and found NOT to answer this question: {tried_categories}\n"
        f"FAQ categories not yet checked: {remaining}\n\n"
        "Pick exactly one next action: BROADEN (try another FAQ category from the "
        "not-yet-checked list), CLARIFY (ask the customer a clarifying question), "
        "or ESCALATE (this needs a human, no FAQ category will help). "
        "Reply with only one word: BROADEN, CLARIFY, or ESCALATE."
    )
    raw = generate(prompt).strip().upper()
    for action in ("BROADEN", "CLARIFY", "ESCALATE"):
        if action in raw:
            return action
    return "ESCALATE"  # honest fallback if the model's reply didn't parse


def agent_answer(query: str, max_steps: int = MAX_AGENT_STEPS) -> dict:
    """The agent: a loop where the model's own judgment decides what happens next."""
    trace = []
    tried_categories: list[str] = []

    category = classify_intent(query)
    for step in range(1, max_steps + 1):
        faq_entry = retrieve_faq(category)
        sufficient = faq_answers_query(query, faq_entry)
        trace.append({"step": step, "category": category, "faq_entry": faq_entry, "sufficient": sufficient})

        if sufficient:
            answer = generate_response(query, faq_entry)
            return {"outcome": "answered", "answer": answer, "trace": trace, "steps": step}

        tried_categories.append(category)
        action = decide_next_action(query, tried_categories)
        trace[-1]["action_chosen"] = action

        if action == "ESCALATE":
            return {
                "outcome": "escalated",
                "answer": "I don't have a confident answer for this in our FAQ -- escalating to a human agent.",
                "trace": trace,
                "steps": step,
            }
        if action == "CLARIFY":
            return {
                "outcome": "clarify",
                "answer": "Could you say a bit more about what you're trying to do? That'll help me find the right answer.",
                "trace": trace,
                "steps": step,
            }
        # BROADEN: pick a different category and loop again
        remaining = [c for c in FAQ if c not in tried_categories]
        category = remaining[0] if remaining else category

    return {"outcome": "budget_exhausted", "answer": "(ran out of steps)", "trace": trace, "steps": max_steps}


def main() -> None:
    query = (
        "My storage suddenly shows as full even though I deleted a bunch of files "
        "last week, and now I can't upload anything -- is there some sync delay, "
        "or did I lose data?"
    )

    print("=" * 70)
    print("WORKFLOW (fixed pipeline)")
    print("=" * 70)
    wf = workflow_answer(query)
    print(json.dumps(wf, indent=2))

    print()
    print("=" * 70)
    print("AGENT (decision-point loop)")
    print("=" * 70)
    ag = agent_answer(query)
    print(json.dumps(ag, indent=2))


if __name__ == "__main__":
    main()
