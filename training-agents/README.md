# Training Agents: Reward and Credit

Three real pieces of how agents actually get trained with RL — not a training run. Per this project's own standing decision, training content stays conceptual plus a CPU-only toy, no GPU. What's real here: real preference-pair construction from real model completions, and exact, correct implementations of the GRPO and DAPO formulas from their own papers, run against toy reward groups so their real documented failure mode and fix are actually visible in the numbers. Concept write-up: [Training Agents: Reward and Credit](https://dhruvmakwana.github.io/agents-deep-dive/training-agents/).

No framework — the raw Anthropic client throughout, same as the rest of this cookbook. Needs an Anthropic key for the first demo only.

## The four demos

- **DPO pair construction** (`dpo_pair_demo`): two real, independently sampled completions to the same prompt, ranked by a real judge call into a real `(chosen, rejected)` preference pair — exactly the training-data shape DPO consumes.
- **GRPO's group-relative advantage** (`grpo_advantages`, `grpo_demo`): DeepSeekMath's own formula — subtract the group mean, divide by the group standard deviation, no critic model — run against a real mixed-reward group and a real degenerate (all-identical-reward) group.
- **DAPO's dynamic sampling** (`dynamic_sample`, `dapo_demo`): the real documented fix for the degenerate-group case above — over-sample and filter out any group whose accuracy is exactly 0 or exactly 1, keeping only groups that produce a real gradient.
- **Outcome-only vs. process credit assignment** (`credit_assignment_demo`): a toy 3-step trajectory where only the middle step is genuinely at fault — showing concretely what each credit-assignment approach can and can't distinguish.

## What actually happened, run against Claude Haiku 4.5

**DPO pair construction**: two real completions to *"Write a one-sentence tagline for a fictional productivity app called Nimbus"* — *"Nimbus: Your thoughts organized, your tasks flowing, your potential limitless."* and *"Nimbus: Rise above the chaos and let your tasks drift into focus."* A real judge call picked the second: *"B is more concrete and specific with vivid metaphors ('drift into focus', 'rise above chaos') that better differentiate the product, while A relies on generic aspirational language that could apply to almost any productivity tool."* Real `(chosen, rejected)` pair constructed from that verdict — no temperature was set explicitly (this SDK version's Messages API has no top-level `temperature` parameter at all), and default sampling still produced two genuinely different completions.

**GRPO's group-relative advantage**: a mixed group of 8 rewards `[1,1,0,1,0,0,1,0]` produced real, differentiated advantages `[1.0, 1.0, -1.0, 1.0, -1.0, -1.0, 1.0, -1.0]` — every reward-1 sample gets positive advantage, every reward-0 sample gets negative, exactly matching the paper's formula. A degenerate group where every sample got the same reward (`[1,1,1,1,1,1,1,1]`, a prompt the model already always answers correctly) produced `[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]` — a real, exact reproduction of DAPO's own named "gradient-decreasing problem": zero variance means zero advantage means zero policy gradient from that group, regardless of how many samples it has.

**DAPO's dynamic sampling**: given three candidate groups — two degenerate (`[1,1,1,1,1,1,1,1]` twice) and one genuinely mixed (`[1,0,1,1,0,1,0,1]`) — the real filter correctly skipped both degenerate groups and kept the mixed one (accuracy 0.625), computing real, non-degenerate advantages `[0.775, -1.291, 0.775, 0.775, -1.291, 0.775, -1.291, 0.775]` from it.

**Outcome-only vs. process credit assignment**: a toy 3-step trajectory where only step 2 was the actual mistake. Outcome-only credit broadcast the same `-1` to all three steps (`outcome_only_can_distinguish_steps: false`) — indistinguishable from a trajectory where every step was equally bad. Process-level credit correctly assigned `[1, -1, 1]` (`process_reward_can_distinguish_steps: true`) — isolating the actual culprit.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python training_agents.py
```

Runs all four demos in sequence and prints each result as JSON. Only the first demo makes real API calls (3 total); the rest are pure, deterministic Python.

## Files

| File | Role |
|---|---|
| `training_agents.py` | All four demos and the CLI entry point — the file you actually run |
| `training_agents_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
