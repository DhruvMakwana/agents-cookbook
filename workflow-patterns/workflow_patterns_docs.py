"""
Same logic as workflow_patterns.py, split into self-contained blocks with no
cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:chaining]
import json
import re


def _call(model, prompt, max_tokens=400):
    # client.messages.create(...) -- see agent_loop.py for the full call shape.
    ...


def _parse_json(raw: str):
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def chaining_demo(client, model) -> dict:
    """Generate an outline, gate it against a concrete criterion, only expand if the gate passes."""
    outline = _call(
        model,
        "Write a 3-bullet outline for a short explainer on how hash tables achieve "
        "O(1) average-case lookup time, covering: what a hash function does, how "
        "collisions are handled, and why average lookup is O(1).",
    )

    gate_raw = _call(
        model,
        f"Outline:\n{outline}\n\nDoes it cover all three required points? "
        'Reply with strict JSON only: {"hash_function": true/false, "collisions": true/false, "big_o": true/false}',
        max_tokens=100,
    )
    gate = _parse_json(gate_raw)
    passed = bool(gate) and all(gate.values())

    if not passed:
        missing = [k for k, v in (gate or {}).items() if not v]
        return {"outline": outline, "gate": gate, "passed": False, "missing": missing, "final_text": None}

    final_text = _call(model, f"Using ONLY this outline, write a ~150-word explainer:\n{outline}", max_tokens=400)
    return {"outline": outline, "gate": gate, "passed": True, "final_text": final_text}
# --8<-- [end:chaining]


# --8<-- [start:parallelization]
import concurrent.futures
import time

_DIMENSIONS = [
    ("technical accuracy", "Check whether the explanation is factually correct."),
    ("clarity for a beginner", "Check whether someone new to the topic could follow this without getting lost."),
    ("grammar and style", "Check for grammar, spelling, and punctuation issues only."),
]


def _review_dimension(name, instruction, text, client, model):
    prompt = f"Review ONLY for {name}. {instruction}\n\nText:\n{text}\n\nList the specific issues found (or say 'None found'), 2 sentences max."
    return name, _call(model, prompt, max_tokens=200)


def parallelization_demo(text: str, client, model) -> dict:
    """Same review calls, timed sequentially and then concurrently -- the
    speedup IS the point of this pattern, so this recipe measures it rather than asserting it."""
    t0 = time.time()
    for name, instruction in _DIMENSIONS:
        _review_dimension(name, instruction, text, client, model)
    sequential_seconds = time.time() - t0

    t1 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_review_dimension, name, instruction, text, client, model) for name, instruction in _DIMENSIONS]
        parallel_results = dict(f.result() for f in futures)
    parallel_seconds = time.time() - t1

    return {"sequential_seconds": round(sequential_seconds, 2), "parallel_seconds": round(parallel_seconds, 2), "reviews": parallel_results}
# --8<-- [end:parallelization]


# --8<-- [start:orchestrator_workers]
def orchestrator_demo(topic: str, client, planner_model, worker_model) -> dict:
    """The planner decides its OWN sub-questions per topic -- not a fixed
    split chosen ahead of time in code, unlike parallelization above. Run
    this with two different topics and the shape of the split changes with
    the input, which is the actual distinguishing feature of this pattern."""
    plan_raw = _call(
        planner_model,
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
        answer = _call(worker_model, f"Answer in about 60 words: {q}", max_tokens=200)
        worker_answers.append({"question": q, "answer": answer})

    notes = "\n".join(f"- Q: {w['question']}\n  A: {w['answer']}" for w in worker_answers)
    final = _call(worker_model, f"Topic: {topic}\n\nResearch notes:\n{notes}\n\nSynthesize these into one coherent explainer, under 200 words.", max_tokens=400)

    return {"topic": topic, "subquestions": subquestions, "worker_answers": worker_answers, "final": final}
# --8<-- [end:orchestrator_workers]


# --8<-- [start:evaluator_optimizer]
_BANNED_WORDS = {"simple", "easy", "simply", "easily"}


def _evaluate_description(text: str) -> dict:
    """A deterministic evaluator -- not every evaluator in this pattern has to be an LLM call."""
    word_count = len(text.split())
    lowered = text.lower()
    banned_found = [w for w in _BANNED_WORDS if w in lowered]
    return {"ok": word_count <= 20 and not banned_found, "word_count": word_count, "banned_found": banned_found}


def evaluator_optimizer_demo(client, model, max_attempts: int = 3) -> dict:
    attempts = []
    feedback = ""
    for attempt in range(1, max_attempts + 1):
        prompt = (
            "Write ONE sentence (under 20 words) describing a to-do list app. "
            "Do not use the words 'simple', 'easy', 'simply', or 'easily' -- those are banned marketing cliches."
            + (f"\n\nYour previous attempt failed: {feedback}" if feedback else "")
        )
        text = _call(model, prompt, max_tokens=60)
        verdict = _evaluate_description(text)
        attempts.append({"attempt": attempt, "text": text, "verdict": verdict})
        if verdict["ok"]:
            return {"outcome": "passed", "attempts": attempts, "final": text}
        feedback = f"word_count={verdict['word_count']} (limit 20), banned_words_used={verdict['banned_found']}"

    return {"outcome": "budget_exhausted", "attempts": attempts, "final": attempts[-1]["text"]}
# --8<-- [end:evaluator_optimizer]
