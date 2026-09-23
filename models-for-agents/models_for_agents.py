"""
Two real repros comparing model tiers for agentic use: tool-calling
reliability under a deliberately ambiguous request (Haiku 4.5 vs Sonnet 5),
and a real cost/accuracy comparison of three dispatch strategies --
always-cheap, always-capable, and routed -- against a batch of queries with
independently checkable correct answers, including two classic reasoning
traps (the widgets/machines lateral-thinking problem and the bat-and-ball
cognitive-reflection-test problem).

Run: python models_for_agents.py
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-5"


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


# ------------------------------------------------------- Demo 1: tool-calling reliability under ambiguity

_SUBSCRIPTION_TOOLS = [
    {
        "name": "cancel_subscription",
        "description": "Permanently cancels a user's subscription. Billing stops immediately and does not resume automatically.",
        "input_schema": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
    },
    {
        "name": "pause_subscription",
        "description": "Temporarily pauses a user's subscription until a given resume date. Billing stops during the pause and resumes automatically on that date.",
        "input_schema": {
            "type": "object",
            "properties": {"user_id": {"type": "string"}, "resume_date": {"type": "string", "description": "ISO date to resume billing"}},
            "required": ["user_id", "resume_date"],
        },
    },
]

_AMBIGUOUS_REQUEST = (
    "User ID U-8842 here. I'm traveling for the next couple of months and want to stop being "
    "charged while I'm away -- can you sort that out? I'll be back and want it picked back up "
    "starting March 1st."
)

_UNAMBIGUOUS_REQUEST = (
    "User ID U-3301 here. I've decided I don't want this subscription anymore at all -- please "
    "cancel it for good, I won't be coming back."
)


def _tool_call_trial(model: str, user_message: str) -> str | None:
    """Returns the name of the first tool called, or None if no tool was called."""
    response = client.messages.create(
        model=model, max_tokens=500, tools=_SUBSCRIPTION_TOOLS,
        messages=[{"role": "user", "content": user_message}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.name
    return None


def tool_calling_reliability_demo(trials: int = 5) -> dict:
    result = {}
    for label, message, correct_tool in [
        ("ambiguous_but_clearly_pause", _AMBIGUOUS_REQUEST, "pause_subscription"),
        ("unambiguous_cancel", _UNAMBIGUOUS_REQUEST, "cancel_subscription"),
    ]:
        result[label] = {"correct_tool": correct_tool, "haiku": [], "sonnet": []}
        for _ in range(trials):
            result[label]["haiku"].append(_tool_call_trial(HAIKU, message))
        for _ in range(trials):
            result[label]["sonnet"].append(_tool_call_trial(SONNET, message))
        result[label]["haiku_accuracy"] = sum(1 for t in result[label]["haiku"] if t == correct_tool) / trials
        result[label]["sonnet_accuracy"] = sum(1 for t in result[label]["sonnet"] if t == correct_tool) / trials
    return result


# ------------------------------------------------------- Demo 2: routing -- cost/accuracy tradeoff

_QUERIES = [
    {
        "id": "capital",
        "difficulty": "simple",
        "prompt": "What is the capital of France? Answer with just the city name, nothing else.",
        "correct": "paris",
    },
    {
        "id": "uppercase",
        "difficulty": "simple",
        "prompt": "Convert this to uppercase: 'hello world'. Reply with only the converted text.",
        "correct": "hello world",  # _grade compares case-insensitively
    },
    {
        "id": "widgets",
        "difficulty": "complex",
        "prompt": "If 5 machines take 5 minutes to make 5 widgets, how long would 100 machines take to make 100 widgets? Answer with just a number and unit, nothing else.",
        "correct": "5 minutes",
    },
    {
        "id": "bat_and_ball",
        "difficulty": "complex",
        "prompt": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost? Answer with just the dollar amount, nothing else.",
        "correct": "$0.05",
    },
]


def _grade(answer: str, correct: str) -> bool:
    a = answer.strip().lower().replace("$", "").replace(",", "")
    c = correct.strip().lower().replace("$", "").replace(",", "")
    return c in a


def _ask(model: str, prompt: str) -> dict:
    response = client.messages.create(model=model, max_tokens=100, messages=[{"role": "user", "content": prompt}])
    return {"answer": _text(response).strip(), "tokens": response.usage.input_tokens + response.usage.output_tokens}


def _route(query_prompt: str) -> str:
    """A cheap router call: classifies a query as simple (route to Haiku) or complex (route to Sonnet)."""
    response = client.messages.create(
        model=HAIKU, max_tokens=10,
        system=(
            "Classify the following user query as either SIMPLE (a basic factual lookup or "
            "mechanical text transformation, no real reasoning needed) or COMPLEX (requires "
            "multi-step reasoning, arithmetic, or logic, especially anything with a tempting "
            "but wrong shortcut answer). Reply with exactly one word: SIMPLE or COMPLEX."
        ),
        messages=[{"role": "user", "content": query_prompt}],
    )
    text = _text(response).strip().upper()
    return "complex" if "COMPLEX" in text else "simple"


def routing_demo() -> dict:
    result = {"always_haiku": {}, "always_sonnet": {}, "routed": {}}
    total_tokens = {"always_haiku": 0, "always_sonnet": 0, "routed": 0}
    correct_count = {"always_haiku": 0, "always_sonnet": 0, "routed": 0}

    for q in _QUERIES:
        haiku_r = _ask(HAIKU, q["prompt"])
        sonnet_r = _ask(SONNET, q["prompt"])
        routed_to = _route(q["prompt"])
        routed_r = haiku_r if routed_to == "simple" else _ask(SONNET, q["prompt"])

        for key, r in [("always_haiku", haiku_r), ("always_sonnet", sonnet_r), ("routed", routed_r)]:
            total_tokens[key] += r["tokens"]
            is_correct = _grade(r["answer"], q["correct"])
            correct_count[key] += is_correct
            result[key][q["id"]] = {"answer": r["answer"], "correct": is_correct}

        result["routed"][q["id"]]["routed_to"] = routed_to

    return {
        "per_query": result,
        "totals": {
            key: {"total_tokens": total_tokens[key], "correct": correct_count[key], "of": len(_QUERIES)}
            for key in total_tokens
        },
    }


def main() -> None:
    print("=" * 70)
    print("DEMO 1: tool-calling reliability under ambiguity (Haiku 4.5 vs Sonnet 5)")
    print("=" * 70)
    print(json.dumps(tool_calling_reliability_demo(), indent=2))

    print()
    print("=" * 70)
    print("DEMO 2: routing -- cost/accuracy tradeoff across dispatch strategies")
    print("=" * 70)
    print(json.dumps(routing_demo(), indent=2))


if __name__ == "__main__":
    main()
