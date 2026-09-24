"""
Same logic as observability_debugging.py, split into self-contained
blocks for blog embedding via pymdownx.snippets.
"""

import time

# --8<-- [start:buggy-tool]
def get_daily_active_users(product: str) -> dict:
    """A real bug: this returns CUMULATIVE all-time users, not daily active users,
    despite the tool's name and description promising a daily figure. The bug is in
    the tool implementation, not in anything the model does."""
    _CUMULATIVE_USERS = {"Nimbus": 2_340_000}
    return {"product": product, "daily_active_users": _CUMULATIVE_USERS.get(product, 0)}


TOOLS = [{
    "name": "get_daily_active_users",
    "description": "Get yesterday's daily active user count for a product.",
    "input_schema": {"type": "object", "properties": {"product": {"type": "string"}}, "required": ["product"]},
}]

TASK = "What were yesterday's daily active users for 'Nimbus', and is that healthy against our 50,000 DAU target?"
# --8<-- [end:buggy-tool]

# --8<-- [start:trace-emitter]
class Span:
    """Emits real OpenTelemetry GenAI semantic-convention attribute names, not a
    made-up schema -- gen_ai.operation.name, gen_ai.provider.name, gen_ai.tool.name,
    gen_ai.usage.*, gen_ai.input.messages / gen_ai.output.messages (the real spec's
    own place for tool call arguments and results), and error.type."""

    def __init__(self, name: str, attributes: dict):
        self.name = name
        self.attributes = attributes
        self.start = time.time()

    def to_dict(self) -> dict:
        return {"span_name": self.name, "duration_ms": round((time.time() - self.start) * 1000, 2), **self.attributes}


def run_traced(client, model: str, task: str) -> dict:
    spans = []
    messages = [{"role": "user", "content": task}]
    for _ in range(4):
        response = client.messages.create(model=model, max_tokens=600, tools=TOOLS, messages=messages)
        spans.append(Span(f"chat {model}", {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": "anthropic",
            "gen_ai.request.model": model,
            "gen_ai.response.model": response.model,
            "gen_ai.usage.input_tokens": response.usage.input_tokens,
            "gen_ai.usage.output_tokens": response.usage.output_tokens,
            "gen_ai.output.messages": [
                {"type": "text", "text": b.text} if b.type == "text"
                else {"type": "tool_call", "name": b.name, "arguments": b.input} if b.type == "tool_use"
                else {"type": b.type}
                for b in response.content
            ],
        }).to_dict())
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = get_daily_active_users(**block.input)
            span = Span(f"execute_tool {block.name}", {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": block.name,
                "gen_ai.input.messages": block.input,
                "gen_ai.output.messages": result,
            })
            spans.append(span.to_dict())
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})
        messages.append({"role": "user", "content": tool_results})
    return {"spans": spans, "response": response}
# --8<-- [end:trace-emitter]

# --8<-- [start:diagnose]
def diagnose_from_trace_alone(spans: list) -> dict:
    """A real, independent diagnostic pass -- using ONLY the trace's own data,
    with no access to the agent's final answer and no re-running anything --
    checking whether the tool's returned number is plausible for a DAILY figure."""
    for span in spans:
        if span.get("gen_ai.operation.name") != "execute_tool":
            continue
        result = span.get("gen_ai.output.messages", {})
        dau = result.get("daily_active_users")
        if dau is not None and dau > 100_000:  # a daily figure this large for one product is implausible
            return {
                "diagnosable_from_trace_alone": True,
                "flagged_span": span["span_name"],
                "flagged_value": dau,
                "reason": f"get_daily_active_users returned {dau:,} -- implausibly large for a single day, likely a cumulative/all-time figure mislabeled as daily",
            }
    return {"diagnosable_from_trace_alone": False}
# --8<-- [end:diagnose]
