"""
Same logic as multi_agent_systems.py, split into self-contained blocks with
no cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:token_economics]
def _call(prompt, client, model, system=None, max_tokens=600):
    # client.messages.create(...) -- see agent_loop.py for the full call shape.
    ...


QUESTIONS = [
    "Explain, in one paragraph, how a Bloom filter achieves space-efficient set-membership testing.",
    "Explain, in one paragraph, how consistent hashing reduces cache invalidation when nodes are added or removed.",
    "Explain, in one paragraph, how a skip list achieves O(log n) search without tree-style rebalancing.",
]


def single_agent_research(client, model) -> dict:
    prompt = "Answer each of these three independent questions, one paragraph each, clearly labeled:\n\n" + "\n".join(
        f"{i+1}. {q}" for i, q in enumerate(QUESTIONS)
    )
    text, tokens = _call(prompt, client, model, max_tokens=900)
    return {"answer": text, "calls": 1, "total_tokens": tokens}


def multi_agent_research(client, model) -> dict:
    """A lead agent dispatches one subagent per question -- each subagent gets
    its own system framing and answers only its question, blind to the
    other two -- then a synthesis call assembles the combined answer."""
    subagent_system = "You are a research subagent. Answer only the question you are given, thoroughly, in one paragraph."
    subagent_results = []
    total_tokens = 0
    for q in QUESTIONS:
        text, tokens = _call(q, client, model, system=subagent_system, max_tokens=400)
        subagent_results.append(text)
        total_tokens += tokens

    synthesis_prompt = "Combine these three subagent answers into one clearly labeled response, one paragraph each:\n\n" + "\n\n".join(
        f"Subagent {i+1} answer: {r}" for i, r in enumerate(subagent_results)
    )
    final_text, synth_tokens = _call(synthesis_prompt, client, model, max_tokens=900)
    total_tokens += synth_tokens

    return {"answer": final_text, "calls": len(QUESTIONS) + 1, "total_tokens": total_tokens}
# --8<-- [end:token_economics]


# --8<-- [start:consistency_risk]
import re

# A refund paragraph mentions two day-counts (the refund window itself, and
# the trial length it's contrasted against), and a day-count near "trial"
# isn't always in a tight fixed window -- of every "N day(s)" match, pick
# the one with the smallest character distance to any "trial" mention,
# rather than assuming fixed proximity.
_DAY_NUMBER_RE = re.compile(r"(\d+)[\s-]*days?", re.I)
_TRIAL_RE = re.compile(r"trial", re.I)


def _extract_trial_length(text: str):
    trial_positions = [m.start() for m in _TRIAL_RE.finditer(text)]
    if not trial_positions:
        return None
    best = None
    best_distance = None
    for match in _DAY_NUMBER_RE.finditer(text):
        distance = min(abs(match.start() - p) for p in trial_positions)
        if best_distance is None or distance < best_distance:
            best, best_distance = int(match.group(1)), distance
    return best


# Deliberately asks for an unusual day-count, not a common default like 7,
# 14, or 30 -- those have strong enough cultural conventions that two
# independent guesses would likely converge by default, which wouldn't
# test the actual risk of two blind subagents inventing different values.
PRICING_INSTRUCTION = (
    "Write one short FAQ paragraph for a fictional app called Nimbus, under the heading 'Pricing'. "
    "Mention that new users get a free trial before being charged, and state how many days the trial lasts "
    "(there is no official policy yet -- pick a specific, slightly unusual number of days, not a common "
    "default like 7, 14, or 30)."
)
REFUND_INSTRUCTION = (
    "Write one short FAQ paragraph for a fictional app called Nimbus, under the heading 'Refunds'. "
    "Explain the refund window, and mention that no refund is needed during the free trial period -- "
    "reference how many days the trial lasts (there is no official policy yet -- pick a specific, slightly "
    "unusual number of days, not a common default like 7, 14, or 30)."
)


def single_agent_faq(client, model) -> dict:
    """One agent writes both sections in the same pass -- whatever trial
    length it invents, it invents once and can reuse."""
    prompt = f"{PRICING_INSTRUCTION}\n\n{REFUND_INSTRUCTION}\n\nWrite both sections."
    text, tokens = _call(prompt, client, model, max_tokens=500)
    sections = text.split("Refund")
    pricing_section = sections[0]
    refund_section = "Refund" + sections[1] if len(sections) > 1 else text
    pricing_trial = _extract_trial_length(pricing_section)
    refund_trial = _extract_trial_length(refund_section)
    return {
        "full_text": text, "tokens": tokens,
        "pricing_trial_days": pricing_trial, "refund_trial_days": refund_trial,
        "consistent": pricing_trial is not None and pricing_trial == refund_trial,
    }


def multi_agent_faq(client, model) -> dict:
    """Two subagents, each blind to the other's output -- exactly the
    scenario Cognition's post argues breaks down: 'actions carry implicit
    decisions, and conflicting decisions carry bad results.'"""
    pricing_text, pricing_tokens = _call(PRICING_INSTRUCTION, client, model, max_tokens=250)
    refund_text, refund_tokens = _call(REFUND_INSTRUCTION, client, model, max_tokens=250)
    pricing_trial = _extract_trial_length(pricing_text)
    refund_trial = _extract_trial_length(refund_text)
    return {
        "pricing_text": pricing_text, "refund_text": refund_text,
        "tokens": pricing_tokens + refund_tokens,
        "pricing_trial_days": pricing_trial, "refund_trial_days": refund_trial,
        "consistent": pricing_trial is not None and pricing_trial == refund_trial,
    }
# --8<-- [end:consistency_risk]
