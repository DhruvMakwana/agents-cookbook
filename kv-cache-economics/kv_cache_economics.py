"""
Three real repros of prompt-cache economics against the live Anthropic API:

1. Cache write vs. cache read -- the same stable tools+system prefix, sent
   twice, with real cache_creation_input_tokens / cache_read_input_tokens
   measured from the actual usage response.
2. The invalidation hierarchy (tools -> system -> messages) -- a real
   tool_choice change (should only cost the messages level) contrasted
   with a real tool-definition edit (should invalidate everything).
3. Tool masking vs. removal -- the mid-conversation-tool-changes beta's
   real tool_removal block (tools array stays byte-identical, cache
   survives) contrasted with physically editing the tools array (cache
   does not survive), plus a functional check that the "masked" tool is
   genuinely unusable, not just hidden.

Run: python kv_cache_economics.py
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"
OPUS = "claude-opus-5"  # mid-conversation-tool-changes is not available on Sonnet 5
MID_CONVERSATION_TOOL_CHANGES_BETA = "mid-conversation-tool-changes-2026-07-01"


def _usage(response) -> dict:
    u = response.usage
    return {
        "cache_creation_input_tokens": u.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": u.cache_read_input_tokens or 0,
        "input_tokens": u.input_tokens,
    }


# ------------------------------------------------------- Shared: a cache-stable tool library

RESEARCH_SYSTEM_PROMPT = (
    "You are a research assistant for an internal knowledge base. You help engineers find "
    "documentation, check service status, and look up internal records. Always answer in one "
    "short sentence unless asked for more detail. Never fabricate a document ID, service name, "
    "or record that wasn't returned by a tool call. If a tool returns no result, say so plainly "
    "instead of guessing. Prefer the most specific tool available for a task over a general one. "
    "When multiple tools could apply, pick the one whose description most precisely matches the "
    "user's request, and explain your choice only if asked."
)

_FILLER_TOOL_SPECS = [
    ("search_docs", "Full-text search across internal documentation pages, ranked by relevance to the query."),
    ("get_doc_by_id", "Fetch a single documentation page in full by its exact document ID, including revision history."),
    ("list_recent_incidents", "List incidents reported in the last 24 hours, including severity and current status."),
    ("check_service_status", "Check whether a named internal service is currently healthy, degraded, or down."),
    ("get_oncall_engineer", "Look up who is currently on call for a given team, including their contact channel."),
    ("search_runbooks", "Search operational runbooks by keyword, returning the runbook title and matching section."),
    ("get_deploy_history", "Get the last 10 deployments for a named service, including commit hash and deploy time."),
    ("check_feature_flag", "Check the current value and rollout percentage of a named feature flag."),
    ("search_slack_archives", "Search archived Slack messages by keyword and channel, within the last 90 days."),
    ("get_team_roster", "List the members of a named engineering team, including their role and time zone."),
    ("lookup_api_endpoint", "Look up the base URL, auth scheme, and rate limits for a named internal API."),
    ("get_service_owner", "Look up which team owns a named internal service and their escalation policy."),
    ("search_postmortems", "Search past incident postmortems by keyword, returning the summary and root cause."),
    ("get_dashboard_link", "Get the monitoring dashboard URL for a named service, scoped to the last 24 hours."),
    ("check_certificate_expiry", "Check the expiry date of the TLS certificate for a named internal domain."),
    ("get_service_dependencies", "List the upstream and downstream dependencies of a named internal service."),
    ("search_architecture_decisions", "Search recorded architecture decision records by keyword or affected service."),
    ("get_capacity_forecast", "Get the projected capacity headroom for a named service over the next 30 days."),
]


def _build_tool_library(*, include: list[str] | None = None) -> list[dict]:
    """Builds the tools array. include=None means every tool; otherwise only the named ones."""
    names = include if include is not None else [n for n, _ in _FILLER_TOOL_SPECS]
    tools = []
    for name, description in _FILLER_TOOL_SPECS:
        if name not in names:
            continue
        tools.append({
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The search query or identifier."}},
                "required": ["query"],
            },
        })
    tools[-1]["cache_control"] = {"type": "ephemeral"}
    return tools


def _cached_system() -> list:
    return [{"type": "text", "text": RESEARCH_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]


# ------------------------------------------------------- Demo 1 + 2: cache economics and the invalidation hierarchy

def cache_economics_and_hierarchy_demo() -> dict:
    tools = _build_tool_library()
    system = _cached_system()
    result = {}

    # Call 1: cold cache -- expect a cache WRITE
    r1 = client.messages.create(
        model=SONNET, max_tokens=100, tools=tools, system=system,
        messages=[{"role": "user", "content": "In one sentence, summarize what you can help with."}],
    )
    result["call_1_cold_write"] = _usage(r1)

    # Call 2: byte-identical tools+system prefix, different user message -- expect a cache READ
    r2 = client.messages.create(
        model=SONNET, max_tokens=100, tools=tools, system=system,
        messages=[{"role": "user", "content": "In one sentence, what's the incident-listing tool called?"}],
    )
    result["call_2_warm_read"] = _usage(r2)

    # Call 3: same tools+system, but tool_choice changed -- per Anthropic's docs, this should
    # only affect the messages level; the tools+system cache read should be unaffected
    r3 = client.messages.create(
        model=SONNET, max_tokens=100, tools=tools, system=system, tool_choice={"type": "any"},
        messages=[{"role": "user", "content": "Check the status of the billing service."}],
    )
    result["call_3_tool_choice_changed"] = _usage(r3)

    # Call 4: one tool's description is edited by a single word -- per Anthropic's docs, this
    # invalidates the ENTIRE cache (tools, system, and messages)
    tools_modified = _build_tool_library()
    tools_modified[0] = {**tools_modified[0], "description": tools_modified[0]["description"] + " (updated)"}
    tools_modified[-1]["cache_control"] = {"type": "ephemeral"}
    r4 = client.messages.create(
        model=SONNET, max_tokens=100, tools=tools_modified, system=system,
        messages=[{"role": "user", "content": "In one sentence, what's the incident-listing tool called?"}],
    )
    result["call_4_tool_definition_edited"] = _usage(r4)

    return result


# ------------------------------------------------------- Demo 3: tool masking vs. removal

def tool_masking_vs_removal_demo() -> dict:
    result = {}
    tools = _build_tool_library()
    system = _cached_system()

    # Call A: baseline. On a genuinely cold cache this is a WRITE; cache reads refresh the TTL,
    # so repeated runs of this recipe against the same tools+system prefix during development
    # will show this as a READ instead -- report whichever the real response says.
    r_a = client.beta.messages.create(
        model=OPUS, max_tokens=50, tools=tools, system=system,
        betas=[MID_CONVERSATION_TOOL_CHANGES_BETA],
        messages=[{"role": "user", "content": "Say OK."}],
    )
    result["call_a_baseline"] = _usage(r_a)

    # Call B1: MASKING -- the top-level tools array is byte-identical to call A's. A mid-conversation
    # role:"system" message withdraws one tool via tool_removal, referencing it, not redefining it.
    # A role:"system" message must precede an assistant message or end the array, so it ends this one.
    tool_removal_directive = {"role": "system", "content": [
        {"type": "tool_removal", "tool": {"type": "tool_reference", "name": "check_feature_flag"}},
    ]}
    r_b1 = client.beta.messages.create(
        model=OPUS, max_tokens=50, tools=tools, system=system,
        betas=[MID_CONVERSATION_TOOL_CHANGES_BETA],
        messages=[{"role": "user", "content": "Say OK."}, tool_removal_directive],
    )
    result["call_b1_masked_tools_array_unchanged"] = _usage(r_b1)

    # Call B2: continue the SAME conversation with the real assistant reply replayed, then a new
    # user turn -- confirms the cache still holds several turns after the masking directive, not
    # just on the one call where it was issued.
    r_b2 = client.beta.messages.create(
        model=OPUS, max_tokens=50, tools=tools, system=system,
        betas=[MID_CONVERSATION_TOOL_CHANGES_BETA],
        messages=[
            {"role": "user", "content": "Say OK."},
            tool_removal_directive,
            {"role": "assistant", "content": r_b1.content},
            {"role": "user", "content": "Say OK one more time."},
        ],
    )
    result["call_b2_masking_persists_next_turn"] = _usage(r_b2)

    # Functional check: is check_feature_flag genuinely unusable after masking, not just hidden?
    # Force tool_choice to the masked tool by name (system directive ends the array) and see what
    # the real API does.
    try:
        r_forced_masked = client.beta.messages.create(
            model=OPUS, max_tokens=50, tools=tools, system=system,
            betas=[MID_CONVERSATION_TOOL_CHANGES_BETA],
            tool_choice={"type": "tool", "name": "check_feature_flag"},
            messages=[{"role": "user", "content": "Check the value of feature flag new_checkout."}, tool_removal_directive],
        )
        result["forced_masked_tool_call"] = {"succeeded": True, "stop_reason": r_forced_masked.stop_reason}
    except Exception as e:
        result["forced_masked_tool_call"] = {"succeeded": False, "error": str(e)}

    # Call C: REMOVAL (contrast) -- the top-level tools array is physically edited (one tool
    # dropped), a different array than call A's, on the same model/beta setup
    tools_without_flag_tool = _build_tool_library(
        include=[n for n, _ in _FILLER_TOOL_SPECS if n != "check_feature_flag"]
    )
    r_c = client.beta.messages.create(
        model=OPUS, max_tokens=50, tools=tools_without_flag_tool, system=system,
        betas=[MID_CONVERSATION_TOOL_CHANGES_BETA],
        messages=[{"role": "user", "content": "Say OK."}],
    )
    result["call_c_removed_tools_array_edited"] = _usage(r_c)

    return result


def main() -> None:
    print("=" * 70)
    print("DEMO 1+2: cache write/read economics, and the invalidation hierarchy")
    print("=" * 70)
    print(json.dumps(cache_economics_and_hierarchy_demo(), indent=2))

    print()
    print("=" * 70)
    print("DEMO 3: tool masking (tool_removal) vs. removal (editing the tools array)")
    print("=" * 70)
    print(json.dumps(tool_masking_vs_removal_demo(), indent=2))


if __name__ == "__main__":
    main()
