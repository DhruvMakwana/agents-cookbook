"""
Same logic as durable_agent.py, split into self-contained blocks with no
cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:event_log]
import json
import os

LOG_FILE = "durable_agent_log.jsonl"


def append_event(event: dict) -> None:
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def read_log() -> list:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE) as f:
        return [json.loads(line) for line in f if line.strip()]
# --8<-- [end:event_log]


# --8<-- [start:idempotent_tools]
LEDGER_DIR = "ledgers"  # each tool's own durable, idempotency-checked state


def _ledger_path(name: str) -> str:
    os.makedirs(LEDGER_DIR, exist_ok=True)
    return os.path.join(LEDGER_DIR, f"{name}.json")


def _read_ledger(name: str) -> dict:
    path = _ledger_path(name)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _write_ledger(name: str, ledger: dict) -> None:
    with open(_ledger_path(name), "w") as f:
        json.dump(ledger, f)


def charge_card(order_id: str, amount: float) -> dict:
    ledger = _read_ledger("charges")
    if order_id in ledger:
        return {"status": "already charged (idempotent replay)", "charge_id": ledger[order_id]}
    charge_id = f"ch_{order_id}"
    ledger[order_id] = charge_id
    _write_ledger("charges", ledger)
    return {"status": "charged", "charge_id": charge_id, "amount": amount}


def reserve_item(order_id: str, sku: str) -> dict:
    ledger = _read_ledger("reservations")
    if order_id in ledger:
        return {"status": "already reserved (idempotent replay)", "reservation_id": ledger[order_id]}
    reservation_id = f"rsv_{order_id}"
    ledger[order_id] = reservation_id
    _write_ledger("reservations", ledger)
    return {"status": "reserved", "reservation_id": reservation_id, "sku": sku}


def send_confirmation(order_id: str) -> dict:
    ledger = _read_ledger("confirmations")
    if order_id in ledger:
        return {"status": "already sent (idempotent replay)", "confirmation_id": ledger[order_id]}
    confirmation_id = f"conf_{order_id}"
    ledger[order_id] = confirmation_id
    _write_ledger("confirmations", ledger)
    return {"status": "sent", "confirmation_id": confirmation_id}
# --8<-- [end:idempotent_tools]


# --8<-- [start:agent_loop]
_IMPLS = {"charge_card": charge_card, "reserve_item": reserve_item, "send_confirmation": send_confirmation}

_TASK = (
    "Process order ORD-8842: charge the card $49.99, reserve item SKU-772, then send an order "
    "confirmation. Do exactly one tool call per turn, in that order, then report done once all "
    "three steps are complete."
)

# Deliberately crash right after this tool's side effect commits, but
# before the fact that it happened gets durably logged -- the exact
# instant a real worker crash is most dangerous for a naive retry.
_CRASH_AFTER_TOOL = "send_confirmation"


def run(client, model, tools, max_steps=6) -> None:
    log = read_log()
    messages = [{"role": "user", "content": _TASK}]
    replayed_steps = 0

    # Reconstruct in-memory conversation state purely from the durable log
    # -- no model call, no tool re-execution, for every step already
    # completed in a prior run.
    for entry in log:
        messages.append({"role": "assistant", "content": entry["assistant_content"]})
        messages.append({"role": "user", "content": entry["tool_result_content"]})
        replayed_steps += 1

    if replayed_steps:
        print(f"[resume] replayed {replayed_steps} completed step(s) -- no new model calls for these.")

    for step in range(replayed_steps, max_steps):
        response = client.messages.create(model=model, max_tokens=400, tools=tools, messages=messages)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            print(f"[done] {final_text}")
            return

        block = next(b for b in response.content if b.type == "tool_use")
        result = _IMPLS[block.name](**block.input)

        # Only crash on the FIRST genuine execution of this step, not on a
        # later idempotent replay -- a real crash happens once, and resume
        # should actually reach completion the second time around.
        is_fresh_execution = not result["status"].startswith("already")
        if block.name == _CRASH_AFTER_TOOL and is_fresh_execution:
            os._exit(1)  # hard exit -- nothing below this line ever runs; the log entry is never written

        tool_result_content = [{"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}]
        messages.append({"role": "user", "content": tool_result_content})
        append_event({"assistant_content": _serialize_content(response.content), "tool_result_content": tool_result_content})


def _serialize_content(content_blocks) -> list:
    """Anthropic content blocks aren't directly JSON-serializable -- convert
    to the plain dicts the API itself accepts back in a later `messages` list."""
    serialized = []
    for block in content_blocks:
        if block.type == "text":
            serialized.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            serialized.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
    return serialized
# --8<-- [end:agent_loop]
