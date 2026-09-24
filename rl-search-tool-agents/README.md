# RL for Search and Tool Agents

A real repro of ToolRL's central, verified claim about reward design for tool-use RL: coarse "answer matching" reward can't tell a close call from a completely wrong one, but a fine-grained, decomposed reward can. Concept write-up: [RL for Search and Tool Agents](https://dhruvmakwana.github.io/agents-deep-dive/rl-search-tool-agents/).

No framework — the raw Anthropic client throughout. Needs an Anthropic key. Haiku 4.5 — the demo is about reward-signal design, not model capability, so the cheap tier is adequate.

## What this recipe can and can't do

Actually running the RL training these papers describe (Search-R1, R1-Searcher, ReSearch, ToolRL, ReTool, RAGEN) needs GPU-hours of policy-gradient training this cookbook doesn't have. What this recipe *can* do honestly: take ToolRL's real, central, verified claim — *"coarse-grained reward signals, such as answer matching, fail to offer the finegrained feedback required for effective learning"* — and compute both reward styles over real Claude tool-call completions, to show concretely what each reward signal can and can't see.

## The repro

Two reward functions, applied to the identical real tool calls:

- **`binary_reward`**: 1.0 if the entire call (tool name + every parameter) exactly matches the expected call, else 0.0 — the coarse "answer matching" ToolRL's abstract names as the failure case.
- **`fine_grained_reward`**: ToolRL's own three-component decomposition — tool name match, parameter-name-set match, parameter-value match — each scored and averaged, so a close call earns partial credit instead of a flat zero.

Four real trials against an identical target action (schedule a 30-minute "Team Sync" event on 2026-10-05), each phrased to elicit a different, real kind of real-world imperfection: fully specified (expect a perfect call), a vaguely-worded duration ("keep it brief"), a request that could plausibly map to a different but available tool (`create_reminder` instead of `create_calendar_event`), and a paraphrased duration ("half an hour").

## What actually happened, run against Claude Haiku 4.5

All four real completions, first attempt, no retries needed:

| Trial | Real call | Binary reward | Fine-grained reward |
|---|---|---|---|
| `fully_specified` | Exact match | **1.0** | **1.0** |
| `vague_duration` | Right tool, right params, `duration_minutes: 15` (guessed) vs. expected `30` | **0.0** | **0.8889** |
| `decoy_tool_available` | Called `create_reminder` instead of `create_calendar_event` | **0.0** | **0.2222** |
| `paraphrased_duration` | Exact match (correctly converted "half an hour" to `30`) | **1.0** | **1.0** |

The real finding is the contrast between `vague_duration` and `decoy_tool_available`: binary reward gives both the identical score — **0.0** — even though one call got the tool right and every parameter right except a single reasonably-guessed value, while the other picked an entirely different tool. A policy trained on binary reward alone gets zero gradient signal distinguishing "almost right" from "completely wrong" on these two real, different real completions. Fine-grained reward gives them real, different scores — 0.8889 vs. 0.2222 — exactly the differentiation ToolRL's own abstract argues coarse reward can't provide.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python rl_search_tool_agents.py
```

Runs all four real trials and prints both reward scores per trial as JSON.

## Files

| File | Role |
|---|---|
| `rl_search_tool_agents.py` | The demo and the CLI entry point — the file you actually run |
| `rl_search_tool_agents_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
