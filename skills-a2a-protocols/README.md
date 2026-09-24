# Skills, A2A and Other Protocols

A real repro of Anthropic's own documented progressive-disclosure claim for Agent Skills. Concept write-up: [Skills, A2A and Other Protocols](https://dhruvmakwana.github.io/agents-deep-dive/skills-a2a-protocols/).

No framework — the raw Anthropic client throughout. Needs an Anthropic key. Sonnet 5.

## The repro

Three fictional skills (`pdf-forms`, `invoice-processing`, `expense-report`), each with a real, sized `SKILL.md`-style body behind a short name+description pair — mirroring Anthropic's own real, documented Skills architecture (Level 1 metadata always loaded, Level 2 full instructions loaded only when triggered). Two real conditions on the identical task, which only actually needs one of the three skills:

- **`all_upfront`**: all three skills' full bodies injected directly into the system prompt on every call, regardless of relevance — the naive approach.
- **`progressive`**: only the three short name+description pairs are in the system prompt; a real `read_skill` tool loads a skill's full body only when the agent decides it's actually needed — mirroring Anthropic's own real progressive disclosure.

## What actually happened, run against Claude Sonnet 5

Real, measured `input_tokens` on the identical task ("walk me through filling out this vendor onboarding PDF form" — relevant to exactly one of the three skills):

| Condition | Real input tokens | Skills actually loaded |
|---|---|---|
| `all_upfront` | **4,975** | All 3 (regardless of relevance) |
| `progressive` | **3,069** (cumulative, 2 real turns) | Only `pdf-forms` — the one actually needed |

A real **38.3% token reduction** on just three candidate skills and a single relevant one. The agent correctly identified `pdf-forms` as the only relevant skill and never loaded `invoice-processing` or `expense-report` at all — confirming Anthropic's own real, documented claim in practice: *"until a Skill is triggered, only its name and description occupy context."* The gap is structural, not tuned for this specific run: `all_upfront`'s cost scales with the *total* number of installed skills regardless of relevance, while `progressive`'s cost scales with the number of skills *actually used* — the more skills installed that aren't relevant to a given task, the wider this real gap gets.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python skills_a2a_protocols.py
```

Runs both real conditions on the identical task and prints real token counts as JSON.

## Files

| File | Role |
|---|---|
| `skills_a2a_protocols.py` | The demo and the CLI entry point — the file you actually run |
| `skills_a2a_protocols_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
