"""
Reasoning paradigms: four mechanisms from the agent-reasoning literature,
each with real code and a real run against a checkable ground truth.

1. Reflexion: solve, verify against a local (non-LLM) check, and if wrong,
   generate a verbal self-reflection and retry with it in context.
2. ReWOO vs ReAct: the same tool-using question solved two ways -- one
   upfront plan with variable substitution (ReWOO), executed deterministically,
   versus a loop that decides one tool call at a time (ReAct) -- with real
   call counts and token counts compared, not just described.
3. LLM Compiler: the same plan ReWOO produced, but dispatching its
   independent steps concurrently instead of one at a time in written order.
4. Plan-and-Solve: a zero-shot *prompting* technique, not an architecture --
   the same word problem solved with a plain "let's think step by step"
   prompt and with an explicit plan-then-solve prompt, compared.

No framework -- the raw Anthropic client throughout, same as
agent-loop-from-scratch and workflow-patterns. Run: python reasoning_paradigms.py
"""

import ast
import concurrent.futures
import json
import operator
import os
import re
import time

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
HAIKU = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
SONNET = "claude-sonnet-5"


def _call(model: str, prompt: str, max_tokens: int = 500):
    """Returns (text, usage_dict). Filters by content-block type rather than
    assuming content[0] is text -- Sonnet 5's adaptive thinking puts a
    ThinkingBlock first, Haiku 4.5 doesn't."""
    response = client.messages.create(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in response.content if b.type == "text")
    usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
    return text, usage


def _parse_json(raw: str):
    match = re.search(r"[\[{].*[\]}]", raw, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------- 1. Reflexion demo

# A state-tracking puzzle: 9 sequential pairwise swaps, deliberately long
# enough that tracking the state by memory alone (rather than writing out
# each intermediate step) tends to lose a swap -- a real, checkable failure
# mode, not a trick question with a memorized "gotcha" answer.
_PEOPLE = ["Nadia", "Omar", "Priya"]
_SWAPS = [
    ("Nadia", "Omar"), ("Omar", "Priya"), ("Nadia", "Priya"),
    ("Nadia", "Omar"), ("Omar", "Priya"), ("Nadia", "Priya"),
    ("Nadia", "Omar"), ("Omar", "Priya"), ("Nadia", "Priya"),
]


def simulate_swaps() -> dict:
    """The ground truth, computed independently of any model."""
    state = {"Nadia": "red", "Omar": "blue", "Priya": "green"}
    for a, b in _SWAPS:
        state[a], state[b] = state[b], state[a]
    return state


def _swap_question() -> str:
    lines = [f"{a} and {b} swap whatever key they are currently holding." for a, b in _SWAPS]
    return (
        "Nadia starts holding the red key, Omar starts holding the blue key, "
        "and Priya starts holding the green key. Then, in this exact order:\n"
        + "\n".join(f"{i+1}. {line}" for i, line in enumerate(lines))
        + "\n\nAfter all the swaps, who holds the red key? "
        "End your answer with a final line in the exact form: Final answer: <name>"
    )


def _extract_name(text: str) -> str:
    match = re.search(r"Final answer:\s*(\w+)", text)
    return match.group(1) if match else ""


def reflexion_demo() -> dict:
    ground_truth = simulate_swaps()
    correct_holder = [name for name, key in ground_truth.items() if key == "red"][0]
    question = _swap_question()

    attempt_1_text, usage_1 = _call(HAIKU, question, max_tokens=600)
    attempt_1_answer = _extract_name(attempt_1_text)

    if attempt_1_answer == correct_holder:
        return {
            "ground_truth": correct_holder,
            "attempt_1": {"answer": attempt_1_answer, "text": attempt_1_text, "correct": True},
            "reflection": None,
            "attempt_2": None,
        }

    reflection_prompt = (
        f"You were asked:\n\n{question}\n\nYou answered:\n\n{attempt_1_text}\n\n"
        "That answer is INCORRECT. Without being told the right answer, reflect in "
        "2-3 sentences on what likely went wrong in how you tracked the swaps, and "
        "what you would do differently to avoid that mistake."
    )
    reflection_text, usage_r = _call(HAIKU, reflection_prompt, max_tokens=300)

    retry_prompt = (
        f"{question}\n\n"
        f"Before answering, here is a reflection on a previous incorrect attempt at "
        f"this exact problem: {reflection_text}\n\n"
        "Now answer carefully, applying that reflection."
    )
    attempt_2_text, usage_2 = _call(HAIKU, retry_prompt, max_tokens=600)
    attempt_2_answer = _extract_name(attempt_2_text)

    return {
        "ground_truth": correct_holder,
        "attempt_1": {"answer": attempt_1_answer, "text": attempt_1_text, "correct": False},
        "reflection": reflection_text,
        "attempt_2": {"answer": attempt_2_answer, "text": attempt_2_text, "correct": attempt_2_answer == correct_holder},
    }


# ------------------------------------------------------- 2/3. ReWOO, ReAct, LLM Compiler

_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Disallowed expression: {ast.dump(node)}")


def calculator(expression: str) -> dict:
    try:
        return {"result": _safe_eval(ast.parse(expression, mode="eval"))}
    except Exception as e:
        return {"error": f"Could not evaluate '{expression}': {e}"}


# Fictional colony records -- fixed, illustrative numbers, not real places.
_COLONY_RECORDS = {
    "Meridian Station": 48200,
    "Halcyon Outpost": 15750,
    "Kepler Reach": 92400,
}


def lookup_population(entity: str, simulate_latency: bool = False) -> dict:
    if simulate_latency:
        # These are in-memory fictional records with no real network call, so
        # there's nothing to actually wait on -- this stands in for the I/O
        # latency a real lookup tool (an API call, a DB query) would have,
        # which is what makes concurrent dispatch worth measuring at all.
        time.sleep(0.4)
    if entity not in _COLONY_RECORDS:
        return {"error": f"No record for '{entity}'"}
    return {"result": _COLONY_RECORDS[entity]}


QUESTION = (
    "Using the colony records, what is the combined population of Meridian Station "
    "and Halcyon Outpost, expressed as a percentage of Kepler Reach's population? "
    "Round to 2 decimal places."
)

_TOOLS = [
    {
        "name": "lookup_population",
        "description": "Look up a colony's population from the colony records. Example: lookup_population('Kepler Reach').",
        "input_schema": {"type": "object", "properties": {"entity": {"type": "string"}}, "required": ["entity"]},
    },
    {
        "name": "calculator",
        "description": "Evaluate a numeric arithmetic expression using +, -, *, /, ** and parentheses.",
        "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
    },
]


def rewoo_demo() -> dict:
    """Plan everything up front (1 call), execute deterministically with
    variable substitution (0 calls), solve from the evidence (1 call)."""
    plan_prompt = (
        f"Question: {QUESTION}\n\n"
        "Produce a plan as a JSON list of steps needed to answer it, using these tools: "
        "lookup_population(entity), calculator(expression). Each step is an object with "
        '"var" (e.g. "E1"), "tool", and "args" (an object). A later step may reference an '
        'earlier result by writing its var name (e.g. "E1") inside a string argument -- '
        "it will be substituted with that step's actual result before execution. "
        "Output ONLY the JSON list, no prose."
    )
    plan_text, usage_plan = _call(SONNET, plan_prompt, max_tokens=500)
    plan = _parse_json(plan_text) or []

    evidence = {}
    for step in plan:
        args = dict(step["args"])
        for key, value in args.items():
            if isinstance(value, str):
                for var, result in evidence.items():
                    value = value.replace(var, str(result))
                args[key] = value
        if step["tool"] == "lookup_population":
            out = lookup_population(args["entity"])
        elif step["tool"] == "calculator":
            out = calculator(args["expression"])
        else:
            out = {"error": f"unknown tool {step['tool']}"}
        evidence[step["var"]] = out.get("result", out.get("error"))

    solve_prompt = (
        f"Question: {QUESTION}\n\nEvidence gathered:\n{json.dumps(evidence, indent=2)}\n\n"
        "Using only this evidence, give the final numeric answer."
    )
    answer_text, usage_solve = _call(SONNET, solve_prompt, max_tokens=200)

    total_calls = 2
    total_tokens = sum(u["input_tokens"] + u["output_tokens"] for u in (usage_plan, usage_solve))
    return {
        "plan": plan, "evidence": evidence, "answer": answer_text,
        "calls": total_calls, "total_tokens": total_tokens,
        "usage": {"plan": usage_plan, "solve": usage_solve},
    }


def react_demo(max_steps: int = 6) -> dict:
    """Classic ReAct: one decision at a time, based on the latest observation.
    Deliberately executes only the FIRST tool call per turn even if the model
    requests several -- native parallel tool use would otherwise let Sonnet
    collapse this into fewer turns, which would test the API's batching, not
    ReAct's actual interleaved-decision mechanism."""
    messages = [{"role": "user", "content": QUESTION}]
    calls_usage = []
    trace = []

    for step in range(1, max_steps + 1):
        response = client.messages.create(model=SONNET, max_tokens=500, tools=_TOOLS, messages=messages)
        calls_usage.append({"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens})
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            total_tokens = sum(u["input_tokens"] + u["output_tokens"] for u in calls_usage)
            return {"answer": final_text, "trace": trace, "calls": len(calls_usage), "total_tokens": total_tokens, "usage": calls_usage}

        blocks = [b for b in response.content if b.type == "tool_use"]
        first, rest = blocks[0], blocks[1:]

        if first.name == "lookup_population":
            result = lookup_population(**first.input)
        else:
            result = calculator(**first.input)
        trace.append({"step": step, "tool": first.name, "arguments": first.input, "result": result})

        tool_results = [{"type": "tool_result", "tool_use_id": first.id, "content": json.dumps(result)}]
        for extra in rest:
            tool_results.append({
                "type": "tool_result", "tool_use_id": extra.id,
                "content": json.dumps({"error": "Not run this turn -- one tool call per turn in this loop."}),
            })
        messages.append({"role": "user", "content": tool_results})

    total_tokens = sum(u["input_tokens"] + u["output_tokens"] for u in calls_usage)
    return {"answer": "(budget exhausted)", "trace": trace, "calls": len(calls_usage), "total_tokens": total_tokens, "usage": calls_usage}


def llm_compiler_demo(plan: list) -> dict:
    """The same plan ReWOO produced, executed differently: steps with no
    dependency on each other's results dispatch concurrently instead of
    strictly in written order."""
    independent_steps = [s for s in plan if not any(re.search(r"\bE\d+\b", str(v)) for v in s["args"].values())]
    dependent_steps = [s for s in plan if s not in independent_steps]

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(independent_steps) or 1) as pool:
        futures = {pool.submit(lookup_population, s["args"]["entity"], True): s["var"] for s in independent_steps if s["tool"] == "lookup_population"}
        evidence = {futures[f]: f.result().get("result") for f in concurrent.futures.as_completed(futures)}
    concurrent_seconds = time.time() - t0

    t1 = time.time()
    for s in independent_steps:
        if s["tool"] == "lookup_population":
            lookup_population(s["args"]["entity"], True)
    sequential_seconds = time.time() - t1

    return {
        "independent_steps": [s["var"] for s in independent_steps],
        "dependent_steps": [s["var"] for s in dependent_steps],
        "evidence": evidence,
        "concurrent_seconds": round(concurrent_seconds, 2),
        "sequential_seconds": round(sequential_seconds, 2),
    }


# ------------------------------------------------------- 4. Plan-and-Solve demo

_WORD_PROBLEM = (
    "A bakery bakes 320 loaves of bread each morning. It sells 3/8 of the loaves by noon, "
    "then donates 20 loaves to a shelter, then sells half of what remains by evening. "
    "The rest goes into the discount bin overnight. Of the loaves in the discount bin, "
    "20% are stale and thrown out the next morning. How many loaves actually make it to "
    "the discount bin's shelf for sale?"
)
_WORD_PROBLEM_GROUND_TRUTH = 72  # 320 -120=200; -20=180; -90(half)=90; -18(20% stale)=72


def plan_and_solve_demo() -> dict:
    zs_cot_prompt = f"{_WORD_PROBLEM}\n\nLet's think step by step."
    zs_cot_text, usage_cot = _call(HAIKU, zs_cot_prompt, max_tokens=500)

    ps_prompt = (
        f"{_WORD_PROBLEM}\n\n"
        "Let's first understand the problem and devise a complete plan. Then, let's carry "
        "out the plan and solve the problem step by step."
    )
    ps_text, usage_ps = _call(HAIKU, ps_prompt, max_tokens=500)

    def _last_number(text: str):
        numbers = re.findall(r"\d+(?:\.\d+)?", text)
        return numbers[-1] if numbers else None

    return {
        "ground_truth": _WORD_PROBLEM_GROUND_TRUTH,
        "zero_shot_cot": {"text": zs_cot_text, "final_number": _last_number(zs_cot_text)},
        "plan_and_solve": {"text": ps_text, "final_number": _last_number(ps_text)},
    }


def main() -> None:
    print("=" * 70)
    print("1. REFLEXION")
    print("=" * 70)
    print(json.dumps(reflexion_demo(), indent=2))

    print()
    print("=" * 70)
    print("2. REWOO vs REACT")
    print("=" * 70)
    rewoo_result = rewoo_demo()
    print("ReWOO:", json.dumps(rewoo_result, indent=2))
    react_result = react_demo()
    print("ReAct:", json.dumps(react_result, indent=2))

    print()
    print("=" * 70)
    print("3. LLM COMPILER (reusing ReWOO's plan)")
    print("=" * 70)
    print(json.dumps(llm_compiler_demo(rewoo_result["plan"]), indent=2))

    print()
    print("=" * 70)
    print("4. PLAN-AND-SOLVE vs ZERO-SHOT-COT")
    print("=" * 70)
    print(json.dumps(plan_and_solve_demo(), indent=2))


if __name__ == "__main__":
    main()
