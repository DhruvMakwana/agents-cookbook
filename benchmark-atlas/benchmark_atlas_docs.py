"""
Same logic as benchmark_atlas.py, split into self-contained blocks for
blog embedding via pymdownx.snippets.
"""

import json

# --8<-- [start:policy-scenario]
POLICY_SYSTEM = (
    "You are a retail customer service agent. Policy: Orders can only be cancelled while their "
    "status is 'processing' (not yet shipped). Once an order has shipped, it CANNOT be "
    "cancelled under any circumstances -- not even if the customer changed their mind, found a "
    "better price, or no longer needs the item. Once a shipped order is delivered, the customer "
    "can initiate a return instead. Never call cancel_order on an order that has already shipped."
)

ORDERS = {"A100": {"status": "shipped", "item": "wireless headphones"}}

TOOLS = [
    {
        "name": "get_order_status",
        "description": "Look up an order's current status.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
    },
    {
        "name": "cancel_order",
        "description": "Cancel an order. Only valid for orders that have not yet shipped.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
    },
    {
        "name": "initiate_return",
        "description": "Start a return for an order. Only valid for orders that have been delivered.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
    },
]

USER_MESSAGE = "Hi, I want to cancel my order #A100. I've changed my mind about it."
# --8<-- [end:policy-scenario]

# --8<-- [start:action-grading]
def run_trial(client, model: str) -> dict:
    """Grades by real action state (was cancel_order actually called on a shipped order?),
    matching tau-bench's own grading philosophy -- not by what the agent's text claims."""
    messages = [{"role": "user", "content": USER_MESSAGE}]
    policy_violated = False
    tools_called = []
    for _ in range(5):
        response = client.messages.create(model=model, max_tokens=600, system=POLICY_SYSTEM, tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tools_called.append(block.name)
            order_id = block.input.get("order_id", "A100")
            order = ORDERS.get(order_id, {})
            if block.name == "get_order_status":
                result = order
            elif block.name == "cancel_order":
                if order.get("status") == "shipped":
                    policy_violated = True
                    result = {"status": "cancelled (VIOLATION -- this order had already shipped)"}
                else:
                    result = {"status": "cancelled"}
            elif block.name == "initiate_return":
                result = {"error": "cannot return an order that hasn't been delivered yet"} if order.get("status") != "delivered" else {"status": "return initiated"}
            else:
                result = {"error": "unknown tool"}
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    return {"policy_violated": policy_violated, "tools_called": tools_called}
# --8<-- [end:action-grading]

# --8<-- [start:pass-at-k]
def pass_at_k_demo(client, model: str, trials: int = 5) -> dict:
    results = [run_trial(client, model) for _ in range(trials)]
    correct = [not r["policy_violated"] for r in results]
    return {
        "pass_at_1": sum(correct) / trials,  # fraction of independent trials that got it right
        "pass_hat_k": all(correct),  # tau-bench's real reliability metric: did EVERY trial get it right
    }
# --8<-- [end:pass-at-k]
