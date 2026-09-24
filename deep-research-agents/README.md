# Deep Research Agents

A real repro of a specific failure mode Anthropic's own engineering blog documents for multi-agent research systems, and their own prescribed fix. Concept write-up: [Deep Research Agents](https://dhruvmakwana.github.io/agents-deep-dive/deep-research-agents/).

No framework — the raw Anthropic client throughout. Needs an Anthropic key. Sonnet 5.

## The repro

Anthropic's own documented failure mode: subagents "performed the exact same searches as other agents... without an effective division of labor." Their own prescribed fix: give each subagent "an objective, an output format, guidance on the tools and sources to use, and clear task boundaries."

A fixed, fictional 6-document corpus on one broad research topic (remote work policy), searchable by 3 real subagents under two conditions:

- **`vague`**: all 3 subagents get the identical, generic instruction — no assigned scope, no boundaries.
- **`scoped`**: each of the 3 subagents gets a distinct, explicitly-bounded objective covering a different third of the topic — Anthropic's own fix, applied literally.

Real measurement: how much real document-retrieval overlap occurs between the 3 subagents under each condition, via a curated (not free-text) keyword search tool.

## What actually happened, run against Claude Sonnet 5

**`vague`** (identical, unscoped instructions to all 3 subagents): the 3 subagents made **10 total real document retrievals** but covered only **4 of 6 unique documents** — every single document that got retrieved was retrieved by more than one subagent. Real redundant-retrieval rate: **60%**. All three subagents independently gravitated toward the same core documents (productivity, cost, culture), each writing a similar, overlapping summary — a direct, real reproduction of Anthropic's documented failure.

**`scoped`** (each subagent given an explicit objective and boundary): the 3 subagents made **7 total real retrievals** and covered **all 6 of 6 unique documents** — the entire corpus, split cleanly across the three subagents with almost no overlap. Real redundant-retrieval rate: **14.3%** (one subagent's search touched a document it then explicitly excluded from its own summary, writing: *"I excluded a document on cross-team collaboration/mentorship, as that falls under culture, outside this research scope"* — respecting the boundary in its output even where its search reached slightly past it).

The real, measured contrast is the finding: identical unscoped instructions produced heavy real redundancy and left 2 of 6 real documents completely uncovered; explicit objectives and boundaries produced full real coverage of the corpus with minimal overlap — Anthropic's own prescribed fix, working as described, on a real (if small) test.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python deep_research_agents.py
```

Runs both real conditions (3 subagents each) and prints each subagent's real retrievals, summary, and the overlap statistics as JSON.

## Files

| File | Role |
|---|---|
| `deep_research_agents.py` | Both conditions and the CLI entry point — the file you actually run |
| `deep_research_agents_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
