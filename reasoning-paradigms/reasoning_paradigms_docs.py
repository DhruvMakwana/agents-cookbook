"""
Same logic as reasoning_paradigms.py, split into self-contained blocks with no
cross-function dependencies, for embedding as live snippets in the blog page.
"""

# --8<-- [start:reflexion]
import re


def _call(model, prompt, max_tokens=500):
    # client.messages.create(...) -- see agent_loop.py for the full call shape.
    ...


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


def reflexion_demo(client, model) -> dict:
    """Solve, check against a local (non-LLM) verifier, and only if wrong,
    reflect in words and retry with the reflection in context."""
    ground_truth = simulate_swaps()
    correct_holder = [name for name, key in ground_truth.items() if key == "red"][0]
    question = _swap_question()

    attempt_1_text = _call(model, question, max_tokens=600)
    attempt_1_answer = _extract_name(attempt_1_text)

    if attempt_1_answer == correct_holder:
        return {"ground_truth": correct_holder, "attempt_1": {"answer": attempt_1_answer, "correct": True}, "reflection": None}

    reflection_prompt = (
        f"You were asked:\n\n{question}\n\nYou answered:\n\n{attempt_1_text}\n\n"
        "That answer is INCORRECT. Without being told the right answer, reflect in "
        "2-3 sentences on what likely went wrong in how you tracked the swaps, and "
        "what you would do differently to avoid that mistake."
    )
    reflection_text = _call(model, reflection_prompt, max_tokens=300)

    retry_prompt = (
        f"{question}\n\nBefore answering, here is a reflection on a previous incorrect "
        f"attempt at this exact problem: {reflection_text}\n\nNow answer carefully, applying that reflection."
    )
    attempt_2_text = _call(model, retry_prompt, max_tokens=600)
    attempt_2_answer = _extract_name(attempt_2_text)

    return {
        "ground_truth": correct_holder,
        "attempt_1": {"answer": attempt_1_answer, "correct": False},
        "reflection": reflection_text,
        "attempt_2": {"answer": attempt_2_answer, "correct": attempt_2_answer == correct_holder},
    }
# --8<-- [end:reflexion]


# --8<-- [start:rewoo]
import ast
import json
import operator

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
    # Deliberately supports only +, -, *, /, ** and parentheses -- no function
    # calls like round(). See this page's real run for what happens when a
    # generated plan assumes more than the tool actually supports.
    try:
        return {"result": _safe_eval(ast.parse(expression, mode="eval"))}
    except Exception as e:
        return {"error": f"Could not evaluate '{expression}': {e}"}


_COLONY_RECORDS = {"Meridian Station": 48200, "Halcyon Outpost": 15750, "Kepler Reach": 92400}


def lookup_population(entity: str) -> dict:
    if entity not in _COLONY_RECORDS:
        return {"error": f"No record for '{entity}'"}
    return {"result": _COLONY_RECORDS[entity]}


def _parse_json(raw: str):
    import re
    match = re.search(r"[\[{].*[\]}]", raw, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


QUESTION = (
    "Using the colony records, what is the combined population of Meridian Station "
    "and Halcyon Outpost, expressed as a percentage of Kepler Reach's population? "
    "Round to 2 decimal places."
)


def rewoo_demo(client, model) -> dict:
    """Plan every tool call up front, with variable substitution across steps
    (1 call) -- execute the plan deterministically (0 calls) -- solve from the
    gathered evidence (1 call). Total: 2 LLM calls, however many tool steps."""
    plan_prompt = (
        f"Question: {QUESTION}\n\n"
        "Produce a plan as a JSON list of steps needed to answer it, using these tools: "
        "lookup_population(entity), calculator(expression). Each step is an object with "
        '"var" (e.g. "E1"), "tool", and "args" (an object). A later step may reference an '
        'earlier result by writing its var name (e.g. "E1") inside a string argument -- '
        "it will be substituted with that step's actual result before execution. "
        "Output ONLY the JSON list, no prose."
    )
    plan_text = _call(model, plan_prompt, max_tokens=500)
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
    answer_text = _call(model, solve_prompt, max_tokens=200)
    return {"plan": plan, "evidence": evidence, "answer": answer_text}
# --8<-- [end:rewoo]


# --8<-- [start:react]
def react_demo(client, model, tools, max_steps=6) -> dict:
    """Classic ReAct: one decision at a time, based on the latest observation.
    Deliberately executes only the FIRST tool call per turn even if the model
    requests several, so native parallel tool-calling can't quietly collapse
    this into fewer turns -- that would test the API, not ReAct's actual
    interleaved-decision mechanism."""
    messages = [{"role": "user", "content": QUESTION}]
    trace = []
    calls = 0

    for step in range(1, max_steps + 1):
        response = client.messages.create(model=model, max_tokens=500, tools=tools, messages=messages)
        calls += 1
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {"answer": final_text, "trace": trace, "calls": calls}

        blocks = [b for b in response.content if b.type == "tool_use"]
        first, rest = blocks[0], blocks[1:]

        result = lookup_population(**first.input) if first.name == "lookup_population" else calculator(**first.input)
        trace.append({"step": step, "tool": first.name, "arguments": first.input, "result": result})

        tool_results = [{"type": "tool_result", "tool_use_id": first.id, "content": json.dumps(result)}]
        for extra in rest:
            tool_results.append({"type": "tool_result", "tool_use_id": extra.id, "content": json.dumps({"error": "Not run this turn."})})
        messages.append({"role": "user", "content": tool_results})

    return {"answer": "(budget exhausted)", "trace": trace, "calls": calls}
# --8<-- [end:react]


# --8<-- [start:llm_compiler]
import concurrent.futures
import time


def llm_compiler_demo(plan: list) -> dict:
    """The same plan ReWOO produced, executed differently: steps with no
    dependency on each other's results dispatch concurrently instead of
    strictly in written order."""
    independent_steps = [s for s in plan if not any(re.search(r"\bE\d+\b", str(v)) for v in s["args"].values())]
    dependent_steps = [s for s in plan if s not in independent_steps]

    def _lookup_with_simulated_latency(entity):
        # These are in-memory fictional records -- nothing to actually wait
        # on. This stands in for the I/O latency a real lookup (an API call,
        # a DB query) would have, which is what makes concurrency worth
        # measuring at all.
        time.sleep(0.4)
        return lookup_population(entity)

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(independent_steps) or 1) as pool:
        futures = {pool.submit(_lookup_with_simulated_latency, s["args"]["entity"]): s["var"] for s in independent_steps if s["tool"] == "lookup_population"}
        evidence = {futures[f]: f.result().get("result") for f in concurrent.futures.as_completed(futures)}
    concurrent_seconds = time.time() - t0

    t1 = time.time()
    for s in independent_steps:
        if s["tool"] == "lookup_population":
            _lookup_with_simulated_latency(s["args"]["entity"])
    sequential_seconds = time.time() - t1

    return {
        "independent_steps": [s["var"] for s in independent_steps],
        "dependent_steps": [s["var"] for s in dependent_steps],
        "concurrent_seconds": round(concurrent_seconds, 2),
        "sequential_seconds": round(sequential_seconds, 2),
    }
# --8<-- [end:llm_compiler]


# --8<-- [start:plan_and_solve]
_WORD_PROBLEM = (
    "A bakery bakes 320 loaves of bread each morning. It sells 3/8 of the loaves by noon, "
    "then donates 20 loaves to a shelter, then sells half of what remains by evening. "
    "The rest goes into the discount bin overnight. Of the loaves in the discount bin, "
    "20% are stale and thrown out the next morning. How many loaves actually make it to "
    "the discount bin's shelf for sale?"
)


def plan_and_solve_demo(client, model) -> dict:
    """The same word problem, two prompts: plain zero-shot chain-of-thought
    versus an explicit plan-then-solve instruction. Plan-and-Solve is a
    prompting technique, not a multi-agent architecture -- this is the
    entire mechanism, one prompt string."""
    zs_cot_text = _call(model, f"{_WORD_PROBLEM}\n\nLet's think step by step.", max_tokens=500)

    ps_prompt = (
        f"{_WORD_PROBLEM}\n\n"
        "Let's first understand the problem and devise a complete plan. Then, let's carry "
        "out the plan and solve the problem step by step."
    )
    ps_text = _call(model, ps_prompt, max_tokens=500)

    return {"zero_shot_cot": zs_cot_text, "plan_and_solve": ps_text}
# --8<-- [end:plan_and_solve]
