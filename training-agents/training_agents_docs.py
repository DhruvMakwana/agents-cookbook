"""
Same logic as training_agents.py, split into self-contained blocks with no
cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:dpo_pair]
def _text(response, client, model):
    # client.messages.create(...) -- see agent_loop.py for the full call shape.
    ...


import json

_PROMPT = "Write a one-sentence tagline for a fictional productivity app called Nimbus."

_JUDGE_INSTRUCTION = (
    "You are judging two taglines for the same fictional product, for clarity and how "
    "specific/concrete (vs generic) they are. Reply with strict JSON only: "
    '{"better": "A" or "B", "reason": "one sentence"}'
)


def dpo_pair_demo(client, model) -> dict:
    # No explicit temperature -- default sampling already produces real
    # variance across independent calls.
    response_a = client.messages.create(model=model, max_tokens=100, messages=[{"role": "user", "content": _PROMPT}])
    response_b = client.messages.create(model=model, max_tokens=100, messages=[{"role": "user", "content": _PROMPT}])
    completion_a, completion_b = _text(response_a, client, model).strip(), _text(response_b, client, model).strip()

    judge_prompt = f"{_JUDGE_INSTRUCTION}\n\nA: {completion_a}\nB: {completion_b}"
    judge_response = client.messages.create(model=model, max_tokens=150, messages=[{"role": "user", "content": judge_prompt}])
    judge_text = _text(judge_response, client, model)
    verdict = json.loads(judge_text[judge_text.index("{"):judge_text.rindex("}") + 1])

    chosen, rejected = (completion_a, completion_b) if verdict["better"] == "A" else (completion_b, completion_a)
    return {
        "completion_a": completion_a, "completion_b": completion_b, "judge_verdict": verdict,
        "dpo_pair": {"prompt": _PROMPT, "chosen": chosen, "rejected": rejected},
    }
# --8<-- [end:dpo_pair]


# --8<-- [start:grpo]
import statistics


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
# --8<-- [end:grpo]


# --8<-- [start:dapo]
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
# --8<-- [end:dapo]


# --8<-- [start:credit_assignment]
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
# --8<-- [end:credit_assignment]
