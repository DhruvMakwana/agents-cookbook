"""
The agent loop from scratch: what actually happens between the model
deciding to call a tool and the tool's result reaching the model again.

No framework, no pluggable-provider wrapper -- this recipe uses the
Anthropic client directly, because seeing the raw request/response shape
is the point. Two real tools (a safe calculator, a fixed-rate currency
converter) and a real tool-calling loop, plus the same question asked
with no tools at all, so the two can be checked against an independently
computed ground truth.

Run: python agent_loop.py
"""

import ast
import json
import operator
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
MAX_ITERATIONS = 6


_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg,
}


def _safe_eval(node):
    """Walk a parsed expression, allowing only numeric literals and +-*/**."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Disallowed expression: {ast.dump(node)}")


def calculate(expression: str) -> dict:
    """A real calculator. Not eval() on model output -- an AST walk that only
    allows numbers and +, -, *, /, ** so a malformed or malicious expression
    can't do anything beyond arithmetic."""
    try:
        tree = ast.parse(expression, mode="eval")
        return {"result": _safe_eval(tree)}
    except Exception as e:
        return {"error": f"Could not evaluate '{expression}': {e}"}


# Fixed, illustrative exchange rates -- not live data, and the tool
# description says so, so the model doesn't treat this as authoritative.
_RATES = {
    ("EUR", "USD"): 1.08, ("USD", "EUR"): 1 / 1.08,
    ("GBP", "USD"): 1.27, ("USD", "GBP"): 1 / 1.27,
    ("USD", "USD"): 1.0,
}


def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    key = (from_currency.upper(), to_currency.upper())
    if key not in _RATES:
        return {"error": f"No exchange rate available for {from_currency} -> {to_currency}"}
    return {"result": round(amount * _RATES[key], 4)}


TOOLS = [
    {
        "name": "calculate",
        "description": (
            "Evaluate a numeric arithmetic expression using +, -, *, /, ** and parentheses. "
            "Example: '127.50 * 1.18' to add an 18% tip to 127.50. "
            "Numbers only -- no currency symbols, no words."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "e.g. '150.45 / 4'"}},
            "required": ["expression"],
        },
    },
    {
        "name": "convert_currency",
        "description": (
            "Convert an amount from one currency to another using this app's fixed exchange "
            "rate table (illustrative rates, not live data). "
            "Example: convert_currency(150.45, 'EUR', 'USD')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "from_currency": {"type": "string", "description": "3-letter code, e.g. 'EUR'"},
                "to_currency": {"type": "string", "description": "3-letter code, e.g. 'USD'"},
            },
            "required": ["amount", "from_currency", "to_currency"],
        },
    },
]

_IMPL = {"calculate": calculate, "convert_currency": convert_currency}


def ask_without_tools(question: str) -> str:
    """The same question, no tools at all -- the baseline this recipe checks
    the tool-using loop against."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text


def run_agent_loop(question: str, max_iterations: int = MAX_ITERATIONS) -> dict:
    """The real loop. Each iteration: send the conversation so far, and if the
    model asked for a tool (stop_reason == "tool_use"), actually run it and
    send the result back as a new message -- the model never touches the
    tool directly, this loop is the only thing that does."""
    messages = [{"role": "user", "content": question}]
    trace = []

    for step in range(1, max_iterations + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {"outcome": "answered", "answer": final_text, "trace": trace, "steps": step}

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn = _IMPL[block.name]
            result = fn(**block.input)
            trace.append({"step": step, "tool": block.name, "arguments": block.input, "result": result})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})

    # Hard budget, hit: return honestly rather than looping forever.
    return {"outcome": "budget_exhausted", "answer": "(ran out of steps)", "trace": trace, "steps": max_iterations}


def main() -> None:
    question = (
        "I'm splitting a EUR127.50 dinner bill among 4 friends, and we want to add "
        "an 18% tip on top before splitting. What does each person owe, in US dollars?"
    )
    ground_truth = round(127.50 * 1.18 * 1.08 / 4, 2)

    print("=" * 70)
    print("BASELINE (no tools)")
    print("=" * 70)
    print(ask_without_tools(question))

    print()
    print("=" * 70)
    print("AGENT LOOP (real tool calls)")
    print("=" * 70)
    result = run_agent_loop(question)
    print(json.dumps(result, indent=2))

    print()
    print(f"Ground truth (computed independently, not by the model): ${ground_truth}")


if __name__ == "__main__":
    main()
