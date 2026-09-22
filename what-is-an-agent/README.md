# What Is an Agent? (workflow vs. agent)

The same customer-support task, built two ways, to make the "decision point" distinction from the concept page concrete instead of definitional. Concept write-up: [What Is an Agent?](https://dhruvmakwana.github.io/agents-deep-dive/what-is-an-agent/).

Needs an LLM. Defaults to Anthropic (see [Configure](#configure) for where the key goes) — OpenAI and a local Ollama model are also supported through the same pluggable `llm.py` used across this cookbook.

## The two pipelines

- **Workflow** (`workflow_answer`): `classify_intent -> retrieve_faq -> generate_response`. A predefined code path. Whatever category gets classified, the generation step is stuck using that FAQ entry — there's no step where anything can say "this isn't right, try something else."
- **Agent** (`agent_answer`): the same classify and retrieve, plus a judge step ("does this FAQ actually answer the question?") and, if not, a real decision point — the **model itself** picks the next action from `BROADEN` / `CLARIFY` / `ESCALATE`, not a fixed `if/else` written into the pipeline. Capped at 3 steps.

## What actually happened, run against Claude Haiku 4.5

Test query: a customer reports storage showing full right after deleting files and asks whether it's a sync delay or data loss — a question the 5-entry FAQ genuinely doesn't cover (the closest entry is a tier-size FAQ, not a sync/data-loss FAQ). One real run; Haiku is this recipe's default model since every step here is a simple classification or judgment call, not one that needs a more capable model.

Both pipelines' `classify_intent` step picked `storage_limits` — a reasonable guess given the query mentions storage, and the wrong one for what's actually being asked.

**Workflow**, stuck with that FAQ entry, produced:
> "I don't have enough information in the provided FAQ entry to answer your question. The FAQ only states storage limits for different tiers, but doesn't address sync delays, data loss, or why your storage might still show as full after deletion. [...] I'd recommend contacting support directly so they can investigate your account specifically."

A genuinely honest finding worth stating plainly: this is *not* a confidently-wrong answer — the model declined on its own, in the generation step, even though nothing in the workflow asked it to, and named specifically what the FAQ doesn't cover. That's a real result, and it means the standard "naive pipeline confidently invents a wrong answer" framing doesn't automatically hold. What the workflow structurally lacks either way is a **mechanism to act** on that doubt: no matter how uncertain the generation step's wording gets, the pipeline still returns that one message as the final answer to the customer. There's no next step for it to take.

**Agent**, with the same misclassification, ran its explicit judge step, got `sufficient: false`, and the model chose `CLARIFY` — the one real decision point in this minimal design. (The clarifying question that gets sent back is a fixed reply in this version, not model-generated text; what's real is the model choosing that *action* over `BROADEN` or `ESCALATE`.)

That's the concrete version of "a decision point where the model chooses its own next step based on live feedback" — the same initial mistake, same model, but the architecture gives the model somewhere to go with its own doubt, and it used it.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — every recipe reads from it automatically (copy `.env.example` there once if that file doesn't exist yet: `cp ../.env.example ../.env`). To override just this recipe instead, `cp .env.example .env` here.

To use the Ollama path instead of Anthropic, set `LLM_PROVIDER=ollama` and run `ollama pull qwen3:4b` once.

## Run

```bash
python workflow_vs_agent.py
```

Prints both pipelines' full output (including the agent's step-by-step trace) as JSON.

## Files

| File | Role |
|---|---|
| `workflow_vs_agent.py` | Both pipelines + the CLI entry point — the file you actually run |
| `workflow_vs_agent_docs.py` | **Documentation only** — self-contained per-function version for the blog. Not run as a script, not kept in sync automatically. |
| `llm.py` | Pluggable generation — Anthropic / OpenAI / Ollama |
