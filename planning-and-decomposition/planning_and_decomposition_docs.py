"""
Same logic as planning_and_decomposition.py, split into self-contained
blocks for blog embedding via pymdownx.snippets.
"""

# --8<-- [start:release-notes-tools]
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
# --8<-- [end:release-notes-tools]

# --8<-- [start:replan-system-prompts]
NO_REPLAN_SYSTEM = (
    "You are a release-notes assistant. Form a plan up front for how you'll gather the "
    "information, then follow that plan step by step using the available tools. Once you've "
    "committed to a plan, execute it as planned rather than second-guessing each step."
)

REPLAN_SYSTEM = (
    "You are a release-notes assistant. Form a plan up front for how you'll gather the "
    "information, then execute it step by step using the available tools. If a step's result "
    "reveals that an assumption behind your plan was wrong (for example, an expected tag doesn't "
    "exist), stop and revise the rest of your plan to account for what you actually learned, "
    "rather than continuing to execute the original plan as if nothing changed."
)
# --8<-- [end:replan-system-prompts]

# --8<-- [start:granularity-system-prompts]
COARSE_SYSTEM = (
    "You are a release-notes assistant with access to tools. Complete the task in whatever way "
    "you judge best."
)

WELL_SIZED_SYSTEM = (
    "You are a release-notes assistant. Before using any tools, write out a plan with these "
    "steps: (1) find the latest tag, (2) if a tag exists, list PRs merged since it -- if no tag "
    "exists, list all merged PRs instead, (3) draft the changelog from what you found. Then "
    "execute that plan."
)

OVER_GRANULAR_SYSTEM = (
    "You are a release-notes assistant. Before using any tools, write out a highly detailed plan "
    "broken into as many small, specific sub-steps as possible -- for example, separate steps for "
    "connecting to the repository, authenticating, querying for the tag, parsing the tag response, "
    "checking whether the tag is null, querying for PRs, parsing each PR record individually, "
    "formatting each entry, and assembling the final draft. Write out every sub-step explicitly "
    "before executing anything, then execute your plan step by step."
)
# --8<-- [end:granularity-system-prompts]

# --8<-- [start:verifier]
def verify_step(run: dict) -> dict:
    """A minimal verifier-in-the-loop check: did execution actually produce a real,
    checkable changelog, or just plan text with no tool calls behind it? This runs
    against the plan-and-execute loop's own real output, no extra model call needed --
    a verifier's job is to check the result that already happened, not to re-do it."""
    called_draft = any(t["tool"] == "draft_changelog" for t in run["trace"])
    if not called_draft:
        return {"passed": False, "reason": "draft_changelog was never called -- no real output was produced"}
    return {"passed": True, "reason": "draft_changelog was called; a real changelog was produced"}
# --8<-- [end:verifier]
