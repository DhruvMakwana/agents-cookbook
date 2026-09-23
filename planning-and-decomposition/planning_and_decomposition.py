"""
Two real repros of plan-and-execute agent architecture: a replanning
trigger (a planned step's assumption turns out wrong mid-execution, and
the agent must revise the rest of the plan), and the granularity tradeoff
(the same task decomposed too coarse, well-sized, and too fine, measured
on real step count, real token cost, and real task success).

Run: python planning_and_decomposition.py
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


# ------------------------------------------------------- Fictional release-notes data

_TAGS = {}  # "api-gateway" has NO tags -- this repo has never been tagged
_MERGED_PRS = {
    "api-gateway": [
        {"title": "Fix rate limiter off-by-one", "merged_at": "2026-08-02"},
        {"title": "Add request tracing headers", "merged_at": "2026-08-14"},
        {"title": "Upgrade TLS certificate rotation", "merged_at": "2026-09-01"},
    ],
}


def get_latest_tag(repo: str) -> dict:
    tag = _TAGS.get(repo)
    return {"tag": tag} if tag else {"tag": None, "note": "This repo has no tags yet."}


def list_merged_prs_since_tag(repo: str, since_tag: str) -> dict:
    if since_tag is None:
        return {"error": "since_tag is required and was not provided"}
    return {"prs": []}  # no tag exists, so "since tag X" can never match anything real


def list_all_merged_prs(repo: str) -> dict:
    return {"prs": _MERGED_PRS.get(repo, [])}


def draft_changelog(entries: list) -> dict:
    return {"changelog": "\n".join(f"- {e}" for e in entries)}


_TOOLS = [
    {
        "name": "get_latest_tag",
        "description": "Get the latest git tag for a repo. May return null if the repo has never been tagged.",
        "input_schema": {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]},
    },
    {
        "name": "list_merged_prs_since_tag",
        "description": "List PRs merged since a specific tag. Requires a real tag; does not work if there is no tag.",
        "input_schema": {"type": "object", "properties": {"repo": {"type": "string"}, "since_tag": {"type": ["string", "null"]}}, "required": ["repo", "since_tag"]},
    },
    {
        "name": "list_all_merged_prs",
        "description": "List every merged PR for a repo, regardless of tags. Use this when there is no tag to anchor a 'since' query.",
        "input_schema": {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]},
    },
    {
        "name": "draft_changelog",
        "description": "Draft changelog text from a list of PR title strings.",
        "input_schema": {"type": "object", "properties": {"entries": {"type": "array", "items": {"type": "string"}}}, "required": ["entries"]},
    },
]

_IMPLS = {
    "get_latest_tag": lambda repo: get_latest_tag(repo),
    "list_merged_prs_since_tag": lambda repo, since_tag: list_merged_prs_since_tag(repo, since_tag),
    "list_all_merged_prs": lambda repo: list_all_merged_prs(repo),
    "draft_changelog": lambda entries: draft_changelog(entries),
}

_TASK = "Prepare the release notes for the 'api-gateway' repo: find what's changed since the last release and draft a changelog."


def _run_loop(system: str, max_turns: int = 8) -> dict:
    messages = [{"role": "user", "content": _TASK}]
    trace = []
    total_tokens = 0
    for _ in range(max_turns):
        response = client.messages.create(model=SONNET, max_tokens=800, system=system, tools=_TOOLS, messages=messages)
        total_tokens += response.usage.input_tokens + response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return {"answer": _text(response), "trace": trace, "total_tokens": total_tokens, "steps": len(trace)}
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            trace.append({"tool": block.name, "input": block.input})
            result = _IMPLS[block.name](**block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    return {"answer": "(budget exhausted)", "trace": trace, "total_tokens": total_tokens, "steps": len(trace)}


# ------------------------------------------------------- Demo 1: replanning trigger

_NO_REPLAN_SYSTEM = (
    "You are a release-notes assistant. Form a plan up front for how you'll gather the "
    "information, then follow that plan step by step using the available tools. Once you've "
    "committed to a plan, execute it as planned rather than second-guessing each step."
)

_REPLAN_SYSTEM = (
    "You are a release-notes assistant. Form a plan up front for how you'll gather the "
    "information, then execute it step by step using the available tools. If a step's result "
    "reveals that an assumption behind your plan was wrong (for example, an expected tag doesn't "
    "exist), stop and revise the rest of your plan to account for what you actually learned, "
    "rather than continuing to execute the original plan as if nothing changed."
)


def replanning_demo() -> dict:
    return {
        "no_replan_instruction": _run_loop(_NO_REPLAN_SYSTEM),
        "replan_instruction": _run_loop(_REPLAN_SYSTEM),
    }


# ------------------------------------------------------- Demo 2: granularity tradeoff

_COARSE_SYSTEM = (
    "You are a release-notes assistant with access to tools. Complete the task in whatever way "
    "you judge best."
)

_WELL_SIZED_SYSTEM = (
    "You are a release-notes assistant. Before using any tools, write out a plan with these "
    "steps: (1) find the latest tag, (2) if a tag exists, list PRs merged since it -- if no tag "
    "exists, list all merged PRs instead, (3) draft the changelog from what you found. Then "
    "execute that plan."
)

_OVER_GRANULAR_SYSTEM = (
    "You are a release-notes assistant. Before using any tools, write out a highly detailed plan "
    "broken into as many small, specific sub-steps as possible -- for example, separate steps for "
    "connecting to the repository, authenticating, querying for the tag, parsing the tag response, "
    "checking whether the tag is null, querying for PRs, parsing each PR record individually, "
    "formatting each entry, and assembling the final draft. Write out every sub-step explicitly "
    "before executing anything, then execute your plan step by step."
)


def _verify_step(run: dict) -> dict:
    """A minimal verifier-in-the-loop check: did execution actually produce a real,
    checkable changelog, or just plan text with no tool calls behind it? This runs
    against the plan-and-execute loop's own real output, no extra model call needed --
    a verifier's job is to check the result that already happened, not to re-do it."""
    called_draft = any(t["tool"] == "draft_changelog" for t in run["trace"])
    if not called_draft:
        return {"passed": False, "reason": "draft_changelog was never called -- no real output was produced"}
    return {"passed": True, "reason": "draft_changelog was called; a real changelog was produced"}


def granularity_demo() -> dict:
    result = {}
    for label, system in [
        ("too_coarse", _COARSE_SYSTEM),
        ("well_sized", _WELL_SIZED_SYSTEM),
        ("over_granular", _OVER_GRANULAR_SYSTEM),
    ]:
        run = _run_loop(system)
        result[label] = {
            "steps": run["steps"],
            "total_tokens": run["total_tokens"],
            "tools_called": [t["tool"] for t in run["trace"]],
            "answer": run["answer"],
            "verifier": _verify_step(run),
        }
    return result


def main() -> None:
    print("=" * 70)
    print("DEMO 1: replanning trigger (a plan's assumption turns out wrong mid-execution)")
    print("=" * 70)
    print(json.dumps(replanning_demo(), indent=2))

    print()
    print("=" * 70)
    print("DEMO 2: granularity tradeoff -- too coarse, well-sized, over-granular")
    print("=" * 70)
    print(json.dumps(granularity_demo(), indent=2))


if __name__ == "__main__":
    main()
