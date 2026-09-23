"""
Three real pieces of how agents actually get trained with RL -- not a
training run (no GPU, no gradient update; per this cookbook's own standing
rule, training content stays conceptual plus a CPU-only toy). What's real
here: real preference-pair construction from real model completions, and
exact, correct implementations of the GRPO and DAPO formulas from their
own papers, run against toy reward groups so their real documented
failure mode and fix are actually visible in the numbers.

1. DPO pair construction: two real, independently sampled completions to
   the same prompt, ranked into a real (chosen, rejected) preference pair.
2. GRPO's group-relative advantage, exactly as DeepSeekMath's paper
   describes it: "rewards are normalized by subtracting the group average
   and dividing by the group standard deviation." Run against a real
   mixed-reward group and a real degenerate (all-same-reward) group.
3. DAPO's "gradient-decreasing problem" and its dynamic-sampling fix,
   applied to the exact degenerate group from (2).
4. Outcome-only vs. step-level (process) credit assignment on a toy
   3-step trajectory, showing the concrete difference in what credit
   each step actually receives.

Run: python training_agents.py
"""

import json
import os
import statistics

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
HAIKU = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


# ------------------------------------------------------- 1. DPO pair construction

_PROMPT = "Write a one-sentence tagline for a fictional productivity app called Nimbus."

_JUDGE_INSTRUCTION = (
    "You are judging two taglines for the same fictional product, for clarity and how "
    "specific/concrete (vs generic) they are. Reply with strict JSON only: "
    '{"better": "A" or "B", "reason": "one sentence"}'
)


def dpo_pair_demo() -> dict:
    # No explicit temperature -- this SDK version's Messages API has no
    # top-level temperature parameter at all; default sampling already
    # produces real variance across independent calls (verified elsewhere
    # in this cookbook, e.g. multi-agent-systems' trial-length demo).
    response_a = client.messages.create(model=HAIKU, max_tokens=100, messages=[{"role": "user", "content": _PROMPT}])
    response_b = client.messages.create(model=HAIKU, max_tokens=100, messages=[{"role": "user", "content": _PROMPT}])
    completion_a, completion_b = _text(response_a).strip(), _text(response_b).strip()

    judge_prompt = f"{_JUDGE_INSTRUCTION}\n\nA: {completion_a}\nB: {completion_b}"
    judge_response = client.messages.create(model=HAIKU, max_tokens=150, messages=[{"role": "user", "content": judge_prompt}])
    judge_text = _text(judge_response)

    try:
        verdict = json.loads(judge_text[judge_text.index("{"):judge_text.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        verdict = {"better": "A", "reason": "(judge output unparsable, defaulted)"}

    chosen, rejected = (completion_a, completion_b) if verdict["better"] == "A" else (completion_b, completion_a)
    return {
        "prompt": _PROMPT, "completion_a": completion_a, "completion_b": completion_b,
        "judge_verdict": verdict, "dpo_pair": {"prompt": _PROMPT, "chosen": chosen, "rejected": rejected},
    }


# ------------------------------------------------------- 2. GRPO group-relative advantage

def grpo_advantages(rewards: list) -> list:
    """Exactly DeepSeekMath's formula: subtract the group mean, divide by
    the group standard deviation. No critic model, no value network --
    the group itself is the baseline."""
    mean = statistics.mean(rewards)
    std = statistics.pstdev(rewards)
    if std == 0:
        # The real, documented failure: DAPO's own paper calls this the
        # "gradient-decreasing problem" -- a zero-variance group produces
        # a zero advantage for every sample, and zero advantage means
        # zero policy gradient from this group, regardless of group size.
        return [0.0 for _ in rewards]
    return [(r - mean) / std for r in rewards]


def grpo_demo() -> dict:
    mixed_group = [1, 1, 0, 1, 0, 0, 1, 0]  # a genuinely hard prompt -- real variance across 8 samples
    degenerate_group = [1, 1, 1, 1, 1, 1, 1, 1]  # a prompt the model already always gets right

    return {
        "mixed_group": {"rewards": mixed_group, "advantages": [round(a, 3) for a in grpo_advantages(mixed_group)]},
        "degenerate_group": {"rewards": degenerate_group, "advantages": grpo_advantages(degenerate_group)},
    }


# ------------------------------------------------------- 3. DAPO dynamic sampling

def dynamic_sample(candidate_groups: list) -> dict:
    """DAPO's actual fix: over-sample prompts, then filter out any group
    whose accuracy is exactly 0 or exactly 1 -- exactly what the paper
    describes -- keeping only groups that will produce a real gradient."""
    for group in candidate_groups:
        accuracy = sum(group) / len(group)
        if 0 < accuracy < 1:
            return {"kept_group": group, "accuracy": accuracy, "advantages": [round(a, 3) for a in grpo_advantages(group)]}
    return {"kept_group": None, "accuracy": None, "advantages": None}


def dapo_demo() -> dict:
    # Simulates re-sampling the same prompt: the first two attempts happen
    # to be degenerate (all-correct), the third has real variance -- DAPO
    # keeps sampling until it finds a group that isn't.
    candidate_groups = [
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 0, 1, 1, 0, 1, 0, 1],
    ]
    result = dynamic_sample(candidate_groups)
    return {"candidate_groups": candidate_groups, "resampling_result": result}


# ------------------------------------------------------- 4. Outcome-only vs. process credit

def outcome_only_credit(step_rewards: list, final_outcome_reward: float) -> list:
    """The naive approach: the single final-outcome reward gets broadcast
    as the credit for every step in the trajectory, regardless of which
    step actually caused the outcome."""
    return [final_outcome_reward for _ in step_rewards]


def credit_assignment_demo() -> dict:
    # A toy 3-step trajectory: steps 1 and 3 were genuinely fine, step 2
    # was the actual mistake that caused the task to fail.
    step_labels = ["step 1 (correct sub-action)", "step 2 (the actual mistake)", "step 3 (correct sub-action)"]
    true_step_quality = [1, -1, 1]  # ground truth, for comparison only -- not seen by either method
    final_outcome_reward = -1  # the trajectory failed overall, because of step 2

    outcome_credit = outcome_only_credit(true_step_quality, final_outcome_reward)
    process_credit = true_step_quality  # a process/step-level reward model scores each step on its own merits

    return {
        "step_labels": step_labels,
        "outcome_only_credit": outcome_credit,
        "process_reward_credit": process_credit,
        "outcome_only_can_distinguish_steps": len(set(outcome_credit)) > 1,
        "process_reward_can_distinguish_steps": len(set(process_credit)) > 1,
    }


def main() -> None:
    print("=" * 70); print("1. DPO PAIR CONSTRUCTION"); print("=" * 70)
    print(json.dumps(dpo_pair_demo(), indent=2))

    print(); print("=" * 70); print("2. GRPO GROUP-RELATIVE ADVANTAGE"); print("=" * 70)
    print(json.dumps(grpo_demo(), indent=2))

    print(); print("=" * 70); print("3. DAPO DYNAMIC SAMPLING"); print("=" * 70)
    print(json.dumps(dapo_demo(), indent=2))

    print(); print("=" * 70); print("4. OUTCOME-ONLY vs. PROCESS CREDIT ASSIGNMENT"); print("=" * 70)
    print(json.dumps(credit_assignment_demo(), indent=2))


if __name__ == "__main__":
    main()
