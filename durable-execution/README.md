# Durable Execution

A minimal event-log agent that survives a real crash mid-tool-call without duplicating a side effect — the Temporal/DBOS pattern, from scratch. Concept write-up: [Durable Execution](https://dhruvmakwana.github.io/agents-deep-dive/durable-execution/).

No framework — the raw Anthropic client throughout, same as the rest of this cookbook. Needs an Anthropic key.

## The mechanism

- **An append-only, durable event log** (`durable_agent_log.jsonl`): every completed step's model decision and tool result gets written before the loop moves on.
- **Replay on startup**: before making any new model call, the agent reads the log and reconstructs its exact conversation state from already-completed steps — no model call, no tool re-execution, for anything already logged.
- **A deliberate, real crash**: right after a tool's side effect commits, but before that fact is durably logged — the exact instant a real worker crash is most dangerous for a naive retry.
- **Idempotent tools as the second line of defense**: each side-effecting tool (`charge_card`, `reserve_item`, `send_confirmation`) checks its own persisted ledger, keyed by order ID, before acting — so even if the orchestrator asks it to run again after a crash, it detects the operation already completed and returns the cached result instead of running it twice.

## Run it — two genuinely separate process invocations

```bash
python durable_agent.py   # run 1: processes 2 steps for real, then deliberately crashes mid-step-3
python durable_agent.py   # run 2: a fresh process -- replays steps 1-2 from disk, completes step 3 idempotently
```

## What actually happened, run against Claude Haiku 4.5

**Invocation 1** — real model calls decided and executed all three steps in order:

```
[step 1] real model call decided: charge_card({'order_id': 'ORD-8842', 'amount': 49.99})
[step 1] tool executed: {'status': 'charged', 'charge_id': 'ch_ORD-8842', 'amount': 49.99}
[step 2] real model call decided: reserve_item({'order_id': 'ORD-8842', 'sku': 'SKU-772'})
[step 2] tool executed: {'status': 'reserved', 'reservation_id': 'rsv_ORD-8842', 'sku': 'SKU-772'}
[step 3] real model call decided: send_confirmation({'order_id': 'ORD-8842'})
[step 3] tool executed: {'status': 'sent', 'confirmation_id': 'conf_ORD-8842'}
[crash] simulating a worker crash right after send_confirmation's side effect committed, before this step's completion is durably logged.
```

At this exact point: the confirmation genuinely was sent (its ledger entry exists) — but the event log has only 2 entries, not 3. The process is dead. Nothing about step 3 survived in the durable log.

**Invocation 2**, a completely separate process, reading only what's on disk:

```
[resume] replayed 2 completed step(s) -- no new model calls for these.
[step 3] real model call decided: send_confirmation({'order_id': 'ORD-8842'})
[step 3] tool executed: {'status': 'already sent (idempotent replay)', 'confirmation_id': 'conf_ORD-8842'}
[done] Done! All three steps have been completed successfully for order ORD-8842:
1. ✓ Card charged $49.99 (charge_id: ch_ORD-8842)
2. ✓ Item SKU-772 reserved (reservation_id: rsv_ORD-8842)
3. ✓ Order confirmation sent (confirmation_id: conf_ORD-8842)
```

Steps 1 and 2 cost **zero** new model calls on resume — reconstructed purely from the log. Step 3 needed a new model call (since it was never durably marked complete), and the model asked to send the confirmation again — but `send_confirmation`'s own ledger check caught it: the customer's confirmation was sent exactly once, with one `confirmation_id`, across both crashed and resumed runs combined. Total real API calls for the entire crash-and-resume story: 4.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Files

| File | Role |
|---|---|
| `durable_agent.py` | The full recipe and the CLI entry point — the file you actually run (twice) |
| `durable_agent_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |

`durable_agent_log.jsonl` and `ledgers/` are created at runtime in this folder and are git-ignored — delete them (`rm durable_agent_log.jsonl && rm -rf ledgers`) to start the crash-and-resume story over from scratch.
