"""
Same logic as agent_loop.py, split into self-contained blocks with no
cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:safe_calculator]
import ast
import operator

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
# --8<-- [end:safe_calculator]


# --8<-- [start:currency_tool]
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
# --8<-- [end:currency_tool]


# --8<-- [start:tool_schemas]
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
# --8<-- [end:tool_schemas]


# --8<-- [start:baseline_no_tools]
def ask_without_tools(question: str, client, model: str) -> str:
    """The same question, no tools at all -- the baseline this recipe checks
    the tool-using loop against."""
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text
# --8<-- [end:baseline_no_tools]


# --8<-- [start:agent_loop]
def run_agent_loop(question: str, client, model: str, tools: list, tool_impl: dict, max_iterations: int = 6) -> dict:
    """The real loop. Each iteration: send the conversation so far, and if the
    model asked for a tool (stop_reason == "tool_use"), actually run it and
    send the result back as a new message -- the model never touches the
    tool directly, this loop is the only thing that does."""
    import json
    messages = [{"role": "user", "content": question}]
    trace = []

    for step in range(1, max_iterations + 1):
        response = client.messages.create(model=model, max_tokens=1024, tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {"outcome": "answered", "answer": final_text, "trace": trace, "steps": step}

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn = tool_impl[block.name]
            result = fn(**block.input)
            trace.append({"step": step, "tool": block.name, "arguments": block.input, "result": result})
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})

    # Hard budget, hit: return honestly rather than looping forever.
    return {"outcome": "budget_exhausted", "answer": "(ran out of steps)", "trace": trace, "steps": max_iterations}
# --8<-- [end:agent_loop]
