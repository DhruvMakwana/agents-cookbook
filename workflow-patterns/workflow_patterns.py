"""
Four of Anthropic's five named workflow patterns, each with real code and a
real run (the fifth, routing, is exactly what the what-is-an-agent recipe's
fixed pipeline already demonstrates -- see that recipe instead of repeating
it here).

1. Prompt chaining: a gated sequence -- generate, check a concrete criterion,
   only proceed if it passes.
2. Parallelization (sectioning): the same input reviewed along independent
   dimensions, dispatched concurrently, with real wall-clock timing against
   running the same calls sequentially.
3. Orchestrator-workers: a planning call decides its OWN sub-questions per
   input (not a fixed, developer-chosen split like parallelization), workers
   answer them, a synthesis call combines the results.
4. Evaluator-optimizer: generate, evaluate against a deterministic (non-LLM)
   check, retry with feedback, capped at a hard attempt budget.

No framework -- the raw Anthropic client throughout, same as
agent-loop-from-scratch. Run: python workflow_patterns.py
"""

import concurrent.futures
import json
import os
import re
import time

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
HAIKU = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
SONNET = "claude-sonnet-5"


def _call(model: str, prompt: str, max_tokens: int = 400) -> str:
    response = client.messages.create(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
    # Some models (Sonnet 5, unlike Haiku 4.5) have adaptive thinking on by
    # default, which puts a ThinkingBlock before the TextBlock -- filter by
    # type rather than assuming content[0] is text.
    return "".join(b.text for b in response.content if b.type == "text")


def _parse_json(raw: str):
    """Small models sometimes wrap JSON in prose or markdown fences -- pull
    out the first {...} block rather than assuming the whole reply is clean JSON."""
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- 1. Chaining

def chaining_demo() -> dict:
    """Generate an outline, gate it against a concrete criterion, only expand
    if the gate passes."""
    outline = _call(
        HAIKU,
        "Write a 3-bullet outline (just the bullets, nothing else) for a short "
        "explainer on how hash tables achieve O(1) average-case lookup time. "
        "The outline must plan to cover: what a hash function does, how "
        "collisions are handled, and why average lookup is O(1).",
    )

    gate_raw = _call(
        HAIKU,
        f"Outline:\n{outline}\n\n"
        "Does this outline's plan cover all three of: (a) what a hash function "
        "does, (b) how collisions are handled, (c) why average lookup is O(1)? "
        'Reply with strict JSON only: {"hash_function": true/false, "collisions": true/false, "big_o": true/false}',
        max_tokens=100,
    )
    gate = _parse_json(gate_raw)
    passed = bool(gate) and all(gate.values())

    if not passed:
        missing = [k for k, v in (gate or {}).items() if not v]
        return {"outline": outline, "gate": gate, "passed": False, "missing": missing, "final_text": None}

    final_text = _call(HAIKU, f"Using ONLY this outline, write a ~150-word explainer:\n{outline}", max_tokens=400)
    return {"outline": outline, "gate": gate, "passed": True, "final_text": final_text}


# ---------------------------------------------------------- 2. Parallelization

REVIEW_TEXT = (
    "Binary search works by repeatedly cutting the search space in half. You start "
    "with a sorted array, check the middle element, and if its not what your looking "
    "for, you eliminate half the remaining elements based on whether the target is "
    "bigger or smaller. This continues until you find it or theres nothing left to "
    "check, which means the algorithm needs about log base 2 of n steps for n "
    "elements, way faster then checking each one by one."
)

_DIMENSIONS = [
    ("technical accuracy", "Check whether the explanation of binary search is factually correct."),
    ("clarity for a beginner", "Check whether someone new to the topic could follow this without getting lost."),
    ("grammar and style", "Check for grammar, spelling, and punctuation issues only."),
]


def _review_dimension(name: str, instruction: str) -> tuple:
    prompt = f"Review ONLY for {name}. {instruction}\n\nText:\n{REVIEW_TEXT}\n\nList the specific issues found (or say 'None found'), 2 sentences max."
    return name, _call(HAIKU, prompt, max_tokens=200)


def parallelization_demo() -> dict:
    """Same 3 review calls, timed sequentially and then concurrently."""
    t0 = time.time()
    for name, instruction in _DIMENSIONS:
        _review_dimension(name, instruction)
    sequential_seconds = time.time() - t0

    t1 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_review_dimension, name, instruction) for name, instruction in _DIMENSIONS]
        parallel_results = dict(f.result() for f in futures)
    parallel_seconds = time.time() - t1

    return {
        "sequential_seconds": round(sequential_seconds, 2),
        "parallel_seconds": round(parallel_seconds, 2),
        "reviews": parallel_results,
    }


# ------------------------------------------------------- 3. Orchestrator-workers

def orchestrator_demo(topic: str) -> dict:
    """The planner decides its OWN sub-questions per topic -- not a fixed
    split chosen ahead of time by this code, unlike parallelization above."""
    plan_raw = _call(
        SONNET,
        f"You are planning a short (under 200 words) explainer on: {topic}\n\n"
        "Decide 2 to 4 focused sub-questions that, if each were answered in "
        "about 60 words, would let you assemble a good explainer on this topic. "
        'Reply with strict JSON only: {"subquestions": ["...", "..."]}',
        max_tokens=300,
    )
    plan = _parse_json(plan_raw)
    subquestions = (plan or {}).get("subquestions", [])

    worker_answers = []
    for q in subquestions:
        answer = _call(HAIKU, f"Answer in about 60 words: {q}", max_tokens=200)
        worker_answers.append({"question": q, "answer": answer})

    notes = "\n".join(f"- Q: {w['question']}\n  A: {w['answer']}" for w in worker_answers)
    final = _call(HAIKU, f"Topic: {topic}\n\nResearch notes:\n{notes}\n\nSynthesize these into one coherent explainer, under 200 words.", max_tokens=400)

    return {"topic": topic, "subquestions": subquestions, "worker_answers": worker_answers, "final": final}


# ------------------------------------------------------- 4. Evaluator-optimizer

_BANNED_WORDS = {"simple", "easy", "simply", "easily"}


def _evaluate_description(text: str) -> dict:
    """A deterministic evaluator -- not every evaluator in this pattern has to be an LLM call."""
    word_count = len(text.split())
    lowered = text.lower()
    banned_found = [w for w in _BANNED_WORDS if w in lowered]
    return {"ok": word_count <= 20 and not banned_found, "word_count": word_count, "banned_found": banned_found}


def evaluator_optimizer_demo(max_attempts: int = 3) -> dict:
    attempts = []
    feedback = ""
    for attempt in range(1, max_attempts + 1):
        prompt = (
            "Write ONE sentence (under 20 words) describing a to-do list app. "
            "Do not use the words 'simple', 'easy', 'simply', or 'easily' -- those are banned marketing cliches."
            + (f"\n\nYour previous attempt failed: {feedback}" if feedback else "")
        )
        text = _call(HAIKU, prompt, max_tokens=60)
        verdict = _evaluate_description(text)
        attempts.append({"attempt": attempt, "text": text, "verdict": verdict})
        if verdict["ok"]:
            return {"outcome": "passed", "attempts": attempts, "final": text}
        feedback = f"word_count={verdict['word_count']} (limit 20), banned_words_used={verdict['banned_found']}"

    return {"outcome": "budget_exhausted", "attempts": attempts, "final": attempts[-1]["text"]}


def main() -> None:
    print("=" * 70)
    print("1. PROMPT CHAINING (with a gate)")
    print("=" * 70)
    print(json.dumps(chaining_demo(), indent=2))

    print()
    print("=" * 70)
    print("2. PARALLELIZATION (sectioning, timed)")
    print("=" * 70)
    print(json.dumps(parallelization_demo(), indent=2))

    print()
    print("=" * 70)
    print("3. ORCHESTRATOR-WORKERS -- topic A")
    print("=" * 70)
    print(json.dumps(orchestrator_demo("arrays vs. linked lists"), indent=2))

    print()
    print("=" * 70)
    print("3b. ORCHESTRATOR-WORKERS -- topic B (different shape, to check the split really is dynamic)")
    print("=" * 70)
    print(json.dumps(orchestrator_demo("how binary search achieves O(log n) time"), indent=2))

    print()
    print("=" * 70)
    print("4. EVALUATOR-OPTIMIZER")
    print("=" * 70)
    print(json.dumps(evaluator_optimizer_demo(), indent=2))


if __name__ == "__main__":
    main()
