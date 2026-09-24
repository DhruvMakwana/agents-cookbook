"""
Two real repros of documented agent cost/latency mechanics:

1. Quadratic transcript growth -- a real agent tool loop, run two ways
   (full accumulating history vs. a windowed history that drops old tool
   results), with REAL cumulative input-token counts pulled from the
   Anthropic API's own usage field on every call. Matches the real,
   documented "N(N+1)/2 triangular number" cost trap in naive agent loops.

2. Confidence-based model routing -- a real batch of questions answered
   two ways (always-Sonnet vs. Haiku-first-with-escalation-on-low-
   confidence), with REAL total tokens and REAL correctness measured for
   both, against the real routing claim: escalate to the larger model
   only when the smaller one signals low confidence.

Run: python cost_latency.py
"""

import json
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-5"

# Real, current per-million-token pricing (input, output), USD.
_PRICING = {HAIKU: (1.00, 5.00), SONNET: (2.00, 10.00)}

# ------------------------------------------------------- Demo 1: quadratic transcript growth

_PADDING = "# padding line to simulate a real config file with surrounding noise\n" * 40
_VALUES = [17, 42, 8, 23, 91, 5]
_FILES = {
    f"config_{i}.txt": f"# Service configuration shard {i} of 6\n{_PADDING}CONFIG_VALUE={value}\n"
    for i, value in enumerate(_VALUES, start=1)
}
_TRUE_SUM = sum(_VALUES)

_READ_FILE_TOOL = [{
    "name": "read_file",
    "description": "Read the contents of a named configuration file.",
    "input_schema": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]},
}]

_TRANSCRIPT_TASK = (
    "You have access to 6 configuration files: config_1.txt through config_6.txt. "
    "Read all of them using the read_file tool, then report the SUM of the CONFIG_VALUE "
    "found across all 6 files as a single final number, on its own line, prefixed with 'SUM='. "
    "Important: call read_file for exactly ONE file per response, and wait for that file's "
    "result before requesting the next one -- do not request multiple files in a single response."
)


def _build_sent_messages(full_messages: list, window: int | None) -> list:
    """The windowing logic under test -- pure, no API calls. If window is None, sends the
    full transcript unchanged (the naive condition). Otherwise, any tool_result block more
    than `window` tool-results back gets its content replaced with a short placeholder,
    while the message structure (roles, tool_use ids) stays intact so the API still accepts
    the conversation."""
    if window is None:
        return full_messages

    tool_result_positions = [i for i, m in enumerate(full_messages) if m["role"] == "user" and isinstance(m["content"], list)
                              and any(b.get("type") == "tool_result" for b in m["content"])]
    keep_from = set(tool_result_positions[-window:]) if tool_result_positions else set()

    sent = []
    for i, m in enumerate(full_messages):
        if i in tool_result_positions and i not in keep_from:
            sent.append({
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": b["tool_use_id"], "content": "[older tool result omitted to save context]"}
                    if b.get("type") == "tool_result" else b
                    for b in m["content"]
                ],
            })
        else:
            sent.append(m)
    return sent


def _run_transcript_condition(window: int | None, max_turns: int = 8) -> dict:
    messages = [{"role": "user", "content": _TRANSCRIPT_TASK}]
    cumulative_input_tokens = 0
    per_turn_input_tokens = []
    final_text = ""

    for _ in range(max_turns):
        sent = _build_sent_messages(messages, window)
        response = client.messages.create(model=HAIKU, max_tokens=500, tools=_READ_FILE_TOOL, messages=sent)
        cumulative_input_tokens += response.usage.input_tokens
        per_turn_input_tokens.append(response.usage.input_tokens)
        messages.append({"role": "assistant", "content": response.content})
        final_text = "\n".join(b.text for b in response.content if b.type == "text")
        if response.stop_reason != "tool_use":
            break
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            content = _FILES.get(block.input["filename"], f"Error: {block.input['filename']} not found")
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
        messages.append({"role": "user", "content": tool_results})

    match = re.search(r"SUM=\s*(\d+)", final_text)
    reported_sum = int(match.group(1)) if match else None
    return {
        "turns": len(per_turn_input_tokens),
        "cumulative_input_tokens": cumulative_input_tokens,
        "per_turn_input_tokens": per_turn_input_tokens,
        "correct": reported_sum == _TRUE_SUM,
        "reported_sum": reported_sum,
    }


def quadratic_growth_demo() -> dict:
    return {
        "naive": _run_transcript_condition(window=None),
        "windowed_last_2": _run_transcript_condition(window=2),
    }


# ------------------------------------------------------- Demo 2: confidence-based model routing

_QUESTIONS = [
    {"q": "What is 17 plus 25?", "answer": "42"},
    {"q": "A store's return policy allows returns within 30 days with a receipt. A customer bought an item 45 days ago and lost the receipt but has the original bank statement showing the purchase. Can they return it under a strict reading of the policy?", "answer": "no"},
    {"q": "What is the capital of France?", "answer": "paris"},
    {"q": "A farmer has 17 sheep. All but 9 die. How many sheep does the farmer have left?", "answer": "9"},
    {"q": "If a train leaves at 3:15pm and the journey takes 1 hour 50 minutes, what time does it arrive?", "answer": "5:05"},
    {"q": "Is the word 'strawberry' spelled with two 'r's in a row anywhere in it?", "answer": "no"},
    {"q": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost?", "answer": "0.05"},
    {"q": "What color do you get by mixing blue and yellow paint?", "answer": "green"},
    {"q": "A shirt normally costs $80. It's discounted 25%, then that new price is discounted another 10%. A cashier says the total discount is 35% off the original price. Is the cashier's math correct, and what is the actual final price?", "answer": "54"},
    {"q": "Three boxes are labeled 'apples', 'oranges', and 'apples and oranges' -- but all three labels are wrong. You may pick one fruit from exactly one box to look at, without seeing inside the others. Which single box should you pick from to correctly relabel all three, and how?", "answer": "apples and oranges"},
]

_ANSWER_TOOL = [{
    "name": "submit_answer",
    "description": (
        "Submit your final answer and your genuine confidence in it. Mark confidence as 'low' "
        "whenever the question involves multi-step arithmetic, a classic-seeming riddle that might "
        "have a non-obvious twist, or any reasoning chain where a careless mistake is plausible -- "
        "not just when you're unsure of a fact. Reserve 'high' for cases you'd bet money on."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "The final answer, as short as possible."},
            "confidence": {"type": "string", "enum": ["high", "low"], "description": "Your genuine, calibrated confidence -- not a default."},
        },
        "required": ["answer", "confidence"],
    },
}]


def _cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = _PRICING[model]
    return round(input_tokens / 1_000_000 * in_rate + output_tokens / 1_000_000 * out_rate, 6)


def _ask(model: str, question: str) -> dict:
    response = client.messages.create(
        model=model, max_tokens=1024, tools=_ANSWER_TOOL, tool_choice={"type": "tool", "name": "submit_answer"},
        messages=[{"role": "user", "content": question}],
    )
    block = next(b for b in response.content if b.type == "tool_use")
    return {
        "answer": block.input["answer"],
        "confidence": block.input.get("confidence", "high"),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": _cost_usd(model, response.usage.input_tokens, response.usage.output_tokens),
    }


def _is_correct(item: dict, answer: str) -> bool:
    return item["answer"].lower() in answer.lower()


def routing_demo() -> dict:
    always_sonnet = []
    routed = []

    for item in _QUESTIONS:
        sonnet_result = _ask(SONNET, item["q"])
        always_sonnet.append({**sonnet_result, "correct": _is_correct(item, sonnet_result["answer"])})

        haiku_result = _ask(HAIKU, item["q"])
        if haiku_result["confidence"] == "low":
            escalated = _ask(SONNET, item["q"])
            routed.append({**escalated, "escalated": True, "haiku_confidence": "low",
                            "correct": _is_correct(item, escalated["answer"]),
                            "input_tokens": haiku_result["input_tokens"] + escalated["input_tokens"],
                            "output_tokens": haiku_result["output_tokens"] + escalated["output_tokens"],
                            "cost_usd": round(haiku_result["cost_usd"] + escalated["cost_usd"], 6)})
        else:
            routed.append({**haiku_result, "escalated": False, "haiku_confidence": "high",
                            "correct": _is_correct(item, haiku_result["answer"])})

    def _summarize(trials):
        return {
            "total_input_tokens": sum(t["input_tokens"] for t in trials),
            "total_output_tokens": sum(t["output_tokens"] for t in trials),
            "total_cost_usd": round(sum(t["cost_usd"] for t in trials), 6),
            "correct": sum(1 for t in trials if t["correct"]),
            "total": len(trials),
        }

    return {
        "always_sonnet": {"summary": _summarize(always_sonnet), "trials": always_sonnet},
        "routed": {"summary": _summarize(routed), "trials": routed,
                   "escalated_count": sum(1 for t in routed if t.get("escalated"))},
    }


def main() -> None:
    print("=" * 70)
    print("Demo 1: quadratic transcript growth -- naive vs. windowed context")
    print("=" * 70)
    print(json.dumps(quadratic_growth_demo(), indent=2))

    print()
    print("=" * 70)
    print("Demo 2: confidence-based model routing -- always-Sonnet vs. Haiku-first")
    print("=" * 70)
    print(json.dumps(routing_demo(), indent=2))


if __name__ == "__main__":
    main()
