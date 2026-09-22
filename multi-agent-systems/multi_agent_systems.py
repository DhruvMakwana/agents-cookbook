"""
Anthropic and Cognition both published influential, opposite-leaning posts
about multi-agent systems in mid-2025. This recipe tests both claims
directly, on real toy tasks, rather than just quoting the debate.

1. Token economics (Anthropic's claim): breadth-first, genuinely independent
   sub-questions, answered by one agent versus a lead agent dispatching
   three subagents plus a synthesis call. Real token cost measured.
2. Consistency risk (Cognition's claim): a tightly-coupled task where two
   sections must agree on one shared fact. One agent writing both sections
   in a single pass versus two subagents, each blind to the other's output,
   each independently choosing that fact. Real agreement checked.

No framework -- the raw Anthropic client throughout, same as the rest of
this cookbook. Run: python multi_agent_systems.py
"""

import json
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"


def _call(prompt: str, system: str = None, max_tokens: int = 600):
    kwargs = {"model": SONNET, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    text = "".join(b.text for b in response.content if b.type == "text")
    usage = response.usage.input_tokens + response.usage.output_tokens
    return text, usage


# ------------------------------------------------------- 1. Token economics

QUESTIONS = [
    "Explain, in one paragraph, how a Bloom filter achieves space-efficient set-membership testing.",
    "Explain, in one paragraph, how consistent hashing reduces cache invalidation when nodes are added or removed.",
    "Explain, in one paragraph, how a skip list achieves O(log n) search without tree-style rebalancing.",
]


def single_agent_research() -> dict:
    prompt = "Answer each of these three independent questions, one paragraph each, clearly labeled:\n\n" + "\n".join(
        f"{i+1}. {q}" for i, q in enumerate(QUESTIONS)
    )
    text, tokens = _call(prompt, max_tokens=900)
    return {"answer": text, "calls": 1, "total_tokens": tokens}


def multi_agent_research() -> dict:
    """A lead agent dispatches one subagent per question -- each subagent gets
    its own system framing and answers only its question, blind to the
    other two -- then a synthesis call assembles the combined answer."""
    subagent_system = "You are a research subagent. Answer only the question you are given, thoroughly, in one paragraph."
    subagent_results = []
    total_tokens = 0
    for q in QUESTIONS:
        text, tokens = _call(q, system=subagent_system, max_tokens=400)
        subagent_results.append(text)
        total_tokens += tokens

    synthesis_prompt = "Combine these three subagent answers into one clearly labeled response, one paragraph each:\n\n" + "\n\n".join(
        f"Subagent {i+1} answer: {r}" for i, r in enumerate(subagent_results)
    )
    final_text, synth_tokens = _call(synthesis_prompt, max_tokens=900)
    total_tokens += synth_tokens

    return {"answer": final_text, "calls": len(QUESTIONS) + 1, "total_tokens": total_tokens, "subagent_answers": subagent_results}


# ------------------------------------------------------- 2. Consistency risk

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


def single_agent_faq() -> dict:
    """One agent writes both sections in the same pass -- whatever trial
    length it invents, it invents once and can reuse."""
    prompt = f"{PRICING_INSTRUCTION}\n\n{REFUND_INSTRUCTION}\n\nWrite both sections."
    text, tokens = _call(prompt, max_tokens=500)
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


def multi_agent_faq() -> dict:
    """Two subagents, each blind to the other's output -- exactly the
    scenario Cognition's post argues breaks down: 'actions carry implicit
    decisions, and conflicting decisions carry bad results.'"""
    pricing_text, pricing_tokens = _call(PRICING_INSTRUCTION, max_tokens=250)
    refund_text, refund_tokens = _call(REFUND_INSTRUCTION, max_tokens=250)
    pricing_trial = _extract_trial_length(pricing_text)
    refund_trial = _extract_trial_length(refund_text)
    return {
        "pricing_text": pricing_text, "refund_text": refund_text,
        "tokens": pricing_tokens + refund_tokens,
        "pricing_trial_days": pricing_trial, "refund_trial_days": refund_trial,
        "consistent": pricing_trial is not None and pricing_trial == refund_trial,
    }


def main() -> None:
    print("=" * 70); print("1. TOKEN ECONOMICS: single agent vs. lead + 3 subagents"); print("=" * 70)
    single = single_agent_research()
    multi = multi_agent_research()
    print("Single-agent:", json.dumps({"calls": single["calls"], "total_tokens": single["total_tokens"]}, indent=2))
    print("Multi-agent:", json.dumps({"calls": multi["calls"], "total_tokens": multi["total_tokens"]}, indent=2))
    print(f"Ratio: {multi['total_tokens'] / single['total_tokens']:.2f}x")

    print(); print("=" * 70); print("2. CONSISTENCY RISK: single agent vs. two blind subagents"); print("=" * 70)
    print("Single-agent:", json.dumps(single_agent_faq(), indent=2))
    print("Multi-agent:", json.dumps(multi_agent_faq(), indent=2))


if __name__ == "__main__":
    main()
