"""
A real repro of the actual OpenTelemetry GenAI semantic conventions
(span names, gen_ai.* attribute names) applied to an agent that produces
a confidently wrong final answer while every individual call "succeeds"
-- no exceptions, no errors, stop_reason == "end_turn". This directly
tests the real, current framing: "When your AI agent returns a
confidently wrong answer, your monitoring sees a successful 200
response." (Jamie Mallers, OneUptime, 2026-03-28)

The question this demo answers: can a real, spec-shaped trace let you
diagnose the actual root cause without re-running the agent -- the
"3 a.m." debugging question -- versus a traditional "did the call
succeed" view that can't?

Run: python observability_debugging.py
"""

import json
import os
import time

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"

# ------------------------------------------------------- A real, subtly buggy tool

def get_daily_active_users(product: str) -> dict:
    """A real bug: this returns CUMULATIVE all-time users, not daily active users,
    despite the tool's name and description promising a daily figure. The bug is in
    the tool implementation, not in anything the model does."""
    _CUMULATIVE_USERS = {"Nimbus": 2_340_000}
    return {"product": product, "daily_active_users": _CUMULATIVE_USERS.get(product, 0)}


_TOOLS = [{
    "name": "get_daily_active_users",
    "description": "Get yesterday's daily active user count for a product.",
    "input_schema": {"type": "object", "properties": {"product": {"type": "string"}}, "required": ["product"]},
}]

_TASK = "What were yesterday's daily active users for 'Nimbus', and is that healthy against our 50,000 DAU target?"


# ------------------------------------------------------- A real, spec-shaped trace emitter

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


def run_traced(task: str) -> dict:
    spans = []
    messages = [{"role": "user", "content": task}]
    for _ in range(4):
        response = client.messages.create(model=SONNET, max_tokens=600, tools=_TOOLS, messages=messages)
        spans.append(Span("chat claude-sonnet-5", {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": "anthropic",
            "gen_ai.request.model": SONNET,
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
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    final_text = "".join(b.text for b in response.content if b.type == "text")
    return {
        "traditional_monitoring_view": {"status": "success", "stop_reason": response.stop_reason, "error": None},
        "real_trace": spans,
        "final_answer": final_text,
    }


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


def main() -> None:
    print("=" * 70)
    print("A real repro: a confidently wrong answer that looks like a clean success")
    print("=" * 70)
    result = run_traced(_TASK)
    print(json.dumps(result, indent=2, default=str))

    print()
    print("=" * 70)
    print("Diagnosis using ONLY the real trace -- no re-running, no access to the final answer")
    print("=" * 70)
    print(json.dumps(diagnose_from_trace_alone(result["real_trace"]), indent=2))


if __name__ == "__main__":
    main()
