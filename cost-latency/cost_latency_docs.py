"""
Same logic as cost_latency.py, split into self-contained blocks for blog
embedding via pymdownx.snippets.
"""

# --8<-- [start:files-and-task]
_PADDING = "# padding line to simulate a real config file with surrounding noise\n" * 40
_VALUES = [17, 42, 8, 23, 91, 5]
_FILES = {
    f"config_{i}.txt": f"# Service configuration shard {i} of 6\n{_PADDING}CONFIG_VALUE={value}\n"
    for i, value in enumerate(_VALUES, start=1)
}
_TRUE_SUM = sum(_VALUES)

_TRANSCRIPT_TASK = (
    "You have access to 6 configuration files: config_1.txt through config_6.txt. "
    "Read all of them using the read_file tool, then report the SUM of the CONFIG_VALUE "
    "found across all 6 files as a single final number, on its own line, prefixed with 'SUM='. "
    "Important: call read_file for exactly ONE file per response, and wait for that file's "
    "result before requesting the next one -- do not request multiple files in a single response."
)
# --8<-- [end:files-and-task]

# --8<-- [start:windowing]
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
# --8<-- [end:windowing]

# --8<-- [start:routing-tool]
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
# --8<-- [end:routing-tool]

# --8<-- [start:routing-loop]
def _ask(client, model: str, question: str) -> dict:
    response = client.messages.create(
        model=model, max_tokens=1024, tools=_ANSWER_TOOL, tool_choice={"type": "tool", "name": "submit_answer"},
        messages=[{"role": "user", "content": question}],
    )
    block = next(b for b in response.content if b.type == "tool_use")
    return {"answer": block.input["answer"], "confidence": block.input.get("confidence", "high")}


def _is_correct(item: dict, answer: str) -> bool:
    return item["answer"].lower() in answer.lower()


def routing_demo(client, model_small: str, model_large: str, questions: list) -> dict:
    always_large = []
    routed = []

    for item in questions:
        large_result = _ask(client, model_large, item["q"])
        always_large.append({**large_result, "correct": _is_correct(item, large_result["answer"])})

        small_result = _ask(client, model_small, item["q"])
        if small_result["confidence"] == "low":
            escalated = _ask(client, model_large, item["q"])
            routed.append({**escalated, "escalated": True})
        else:
            routed.append({**small_result, "escalated": False})

    return {"always_large": always_large, "routed": routed}
# --8<-- [end:routing-loop]
