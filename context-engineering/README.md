# Context Engineering

Drew Breunig names four ways context makes an agent worse -- poisoning, distraction, confusion, clash -- and names fixes for each. Cited constantly, reproduced almost nowhere. This recipe builds one minimal, real repro per failure mode, with a real fix applied and a real before/after comparison against an independently computed ground truth. Concept write-up: [Context Engineering](https://dhruvmakwana.github.io/agents-deep-dive/context-engineering/).

No framework -- the raw Anthropic client throughout, same as the rest of this cookbook. Needs an Anthropic key.

## The four repros

- **Poisoning** (`poisoning_demo`, fix: quarantine): a hallucinated founding year enters context as a fake tool result; a later question that depends on it gets the wrong answer. Quarantine = the bad turn is caught and replaced before it can propagate.
- **Distraction** (`distraction_demo`, fix: compress): six prior turns confidently apply a wrong averaging method (divide by N-1 instead of N). Compress = drop that flawed history and ask fresh instead of carrying it forward.
- **Confusion** (`confusion_demo`, fix: select): a task needing one specific tool is given that tool plus a plausible stale-data decoy and 10 unrelated filler tools. Select = only load the tool actually needed.
- **Clash** (`clash_demo`, fix: prune): two contradictory refund-window facts sit in context at once. Prune = remove the stale one once a newer fact supersedes it.

Model choice: all four default to Haiku -- deliberately testing whether even a fast/cheap model exhibits these basic context-management failures.

## What actually happened, run against Claude Haiku 4.5

**Poisoning worked exactly as designed.** Poisoned context (fake founding year 2009): *"As of 2026, Meridian Robotics would be 17 years old (2026 - 2009 = 17 years)."* Quarantined context (corrected to the real 2014): *"...that would make it 12 years old (2026 - 2014 = 12)."* Ground truth: 12. A clean, real failure and a clean, real fix.

**Distraction produced a real failure -- but not the one hypothesized.** With six turns of consistently-wrong "divide by N-1" answers in context, the real answer to a new question was *"The average is 100"* — not 25 (correct) and not 33.33 (what mechanically following the demonstrated N-1 pattern would give). 100 is the raw, undivided sum (10+20+30+40). The exact failure mode wasn't a clean copy of the demonstrated pattern's arithmetic, but the flawed history still produced a real wrong answer, in the same terse, no-work-shown style the six prior turns modeled. With that history dropped (compressed to just the fresh question): *"The average is 25. (10 + 20 + 30 + 40) ÷ 4 = 100 ÷ 4 = 25"* — correct, and showing its work this time. Reported honestly rather than smoothed into matching the prediction.

**Confusion did not reproduce in this run.** Given 12 tools (the correct `get_live_exchange_rate`, a plausible stale-data decoy `get_exchange_rate_estimate`, and 10 unrelated fillers), Claude Haiku 4.5 still called the correct tool and got **216 USD** right — identical to the clean, single-tool condition. An honest negative result: at 12 tools with clearly-differentiated descriptions ("live" vs. "cached... may be stale"), this model wasn't confused. The literature's reported confusion threshold (RAG-MCP: real degradation past 30+ tools) is a scale this demo didn't reach — a fair, disclosed limit of what one minimal repro can show, not evidence the failure mode doesn't exist.

**Clash also did not reproduce as a failure** — arguably because this repro's contradiction was resolvable, not genuinely ambiguous: the two conflicting policy statements were explicitly labeled "v2... supersedes v1," giving the model a real signal to resolve the conflict correctly. Both conditions answered 14 days; the clashing condition's answer even cited the supersession reasoning explicitly: *"According to policy_doc v2 (published Aug 2026, which supersedes v1), the refund window is 14 days."* Worth stating plainly: this demo shows a model correctly using an explicit resolution cue when one is present, not what happens under a genuinely unresolvable clash with no signal of which fact is authoritative — that's a real gap for a future, harder repro, not something to claim was tested here.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python context_engineering.py
```

Runs all four demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `context_engineering.py` | All four demos and the CLI entry point -- the file you actually run |
| `context_engineering_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
