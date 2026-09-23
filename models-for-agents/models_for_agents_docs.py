"""
Same logic as models_for_agents.py, split into self-contained blocks for
blog embedding via pymdownx.snippets.
"""

# --8<-- [start:ambiguous-tools]
SUBSCRIPTION_TOOLS = [
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

AMBIGUOUS_REQUEST = (
    "User ID U-8842 here. I'm traveling for the next couple of months and want to stop being "
    "charged while I'm away -- can you sort that out? I'll be back and want it picked back up "
    "starting March 1st."
)


def tool_call_trial(client, model: str, user_message: str) -> str | None:
    """Returns the name of the first tool called, or None if no tool was called."""
    response = client.messages.create(
        model=model, max_tokens=500, tools=SUBSCRIPTION_TOOLS,
        messages=[{"role": "user", "content": user_message}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.name
    return None
# --8<-- [end:ambiguous-tools]

# --8<-- [start:router]
def route(client, haiku_model: str, query_prompt: str) -> str:
    """A cheap router call: classifies a query as simple (route to a cheap model) or
    complex (route to a more capable model)."""
    response = client.messages.create(
        model=haiku_model, max_tokens=10,
        system=(
            "Classify the following user query as either SIMPLE (a basic factual lookup or "
            "mechanical text transformation, no real reasoning needed) or COMPLEX (requires "
            "multi-step reasoning, arithmetic, or logic, especially anything with a tempting "
            "but wrong shortcut answer). Reply with exactly one word: SIMPLE or COMPLEX."
        ),
        messages=[{"role": "user", "content": query_prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip().upper()
    return "complex" if "COMPLEX" in text else "simple"
# --8<-- [end:router]

# --8<-- [start:reasoning-traps]
QUERIES = [
    {
        "id": "capital",
        "difficulty": "simple",
        "prompt": "What is the capital of France? Answer with just the city name, nothing else.",
        "correct": "paris",
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
# --8<-- [end:reasoning-traps]
