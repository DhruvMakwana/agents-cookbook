"""
The identical tiny tool-calling task, solved three ways, all on the same
Claude model: the raw Anthropic client (own the loop), LangChain/LangGraph's
create_agent, and Pydantic AI's Agent. Real lines of code counted from the
actual solving logic (imports and the shared tool implementation excluded,
since those are identical across all three), real answers checked against
an independently computed ground truth.

Run: python framework_shootout.py
"""

import ast
import operator
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

HAIKU = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
QUESTION = "What is 15% of 240, plus 30?"
GROUND_TRUTH = 0.15 * 240 + 30  # 66.0


# ------------------------------------------------------- Shared tool (identical across all three)

_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Disallowed expression: {ast.dump(node)}")


def calculate(expression: str) -> float:
    """Evaluate a numeric arithmetic expression using + - * / ** and parentheses."""
    return _safe_eval(ast.parse(expression, mode="eval"))


# ------------------------------------------------------- 1. Raw Anthropic client (own the loop)

def run_raw() -> dict:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    tools = [{"name": "calculate", "description": "Evaluate a numeric arithmetic expression.",
              "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}]
    messages = [{"role": "user", "content": QUESTION}]
    calls = 0
    for _ in range(4):
        response = client.messages.create(model=HAIKU, max_tokens=300, tools=tools, messages=messages)
        calls += 1
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return {"answer": "".join(b.text for b in response.content if b.type == "text"), "calls": calls}
        block = next(b for b in response.content if b.type == "tool_use")
        result = calculate(**block.input)
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": block.id, "content": str(result)}]})
    return {"answer": "(budget exhausted)", "calls": calls}


# ------------------------------------------------------- 2. LangChain / LangGraph create_agent

def run_langgraph() -> dict:
    from langchain.agents import create_agent
    from langchain.tools import tool

    calculate_tool = tool(calculate)
    agent = create_agent(f"anthropic:{HAIKU}", tools=[calculate_tool])
    result = agent.invoke({"messages": [{"role": "user", "content": QUESTION}]})
    final_message = result["messages"][-1]
    calls = sum(1 for m in result["messages"] if getattr(m, "type", None) == "ai")
    return {"answer": final_message.content, "calls": calls}


# ------------------------------------------------------- 3. Pydantic AI

def run_pydantic_ai() -> dict:
    from pydantic_ai import Agent

    agent = Agent(f"anthropic:{HAIKU}", tools=[calculate])
    result = agent.run_sync(QUESTION)
    calls = len(result.all_messages()) // 2  # request/response pairs
    return {"answer": result.output, "calls": calls}


def main() -> None:
    print("Ground truth:", GROUND_TRUTH)
    print()
    print("=" * 70); print("1. RAW ANTHROPIC CLIENT"); print("=" * 70)
    print(run_raw())

    print(); print("=" * 70); print("2. LANGCHAIN / LANGGRAPH create_agent"); print("=" * 70)
    print(run_langgraph())

    print(); print("=" * 70); print("3. PYDANTIC AI"); print("=" * 70)
    print(run_pydantic_ai())


if __name__ == "__main__":
    main()
