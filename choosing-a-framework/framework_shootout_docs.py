"""
Same logic as framework_shootout.py, split into self-contained blocks with
no cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:shared_tool]
import ast
import operator

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


QUESTION = "What is 15% of 240, plus 30?"
GROUND_TRUTH = 0.15 * 240 + 30  # 66.0
# --8<-- [end:shared_tool]


# --8<-- [start:raw]
def run_raw(client, model) -> dict:
    tools = [{"name": "calculate", "description": "Evaluate a numeric arithmetic expression.",
              "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}]
    messages = [{"role": "user", "content": QUESTION}]
    calls = 0
    for _ in range(4):
        response = client.messages.create(model=model, max_tokens=300, tools=tools, messages=messages)
        calls += 1
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return {"answer": "".join(b.text for b in response.content if b.type == "text"), "calls": calls}
        block = next(b for b in response.content if b.type == "tool_use")
        result = calculate(**block.input)
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": block.id, "content": str(result)}]})
    return {"answer": "(budget exhausted)", "calls": calls}
# --8<-- [end:raw]


# --8<-- [start:langgraph]
def run_langgraph(model_id: str) -> dict:
    from langchain.agents import create_agent
    from langchain.tools import tool

    calculate_tool = tool(calculate)
    agent = create_agent(f"anthropic:{model_id}", tools=[calculate_tool])
    result = agent.invoke({"messages": [{"role": "user", "content": QUESTION}]})
    final_message = result["messages"][-1]
    calls = sum(1 for m in result["messages"] if getattr(m, "type", None) == "ai")
    return {"answer": final_message.content, "calls": calls}
# --8<-- [end:langgraph]


# --8<-- [start:pydantic_ai]
def run_pydantic_ai(model_id: str) -> dict:
    from pydantic_ai import Agent

    agent = Agent(f"anthropic:{model_id}", tools=[calculate])
    result = agent.run_sync(QUESTION)
    calls = len(result.all_messages()) // 2  # request/response pairs
    return {"answer": result.output, "calls": calls}
# --8<-- [end:pydantic_ai]


# --8<-- [start:crewai]
def run_crewai(model_id: str) -> dict:
    from crewai import LLM, Agent
    from crewai.tools import tool as crewai_tool

    calculate_tool = crewai_tool("calculate")(calculate)
    llm = LLM(model=f"anthropic/{model_id}", max_tokens=300)
    agent = Agent(role="Calculator", goal="Answer the question accurately using the calculate tool.",
                  backstory="A precise assistant that always uses tools for arithmetic.", tools=[calculate_tool], llm=llm, verbose=False)
    result = agent.kickoff(QUESTION)  # direct Agent.kickoff -- no Task/Crew wrapper needed
    calls = result.usage_metrics.get("successful_requests") if result.usage_metrics else None
    return {"answer": result.raw, "calls": calls}
# --8<-- [end:crewai]
