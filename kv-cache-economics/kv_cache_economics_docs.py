"""
Same logic as kv_cache_economics.py, split into self-contained blocks for
blog embedding via pymdownx.snippets.
"""

# --8<-- [start:tool-library]
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


def build_tool_library(*, include: list[str] | None = None) -> list[dict]:
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


def cached_system() -> list:
    return [{"type": "text", "text": RESEARCH_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
# --8<-- [end:tool-library]

# --8<-- [start:cache-write-read]
def cache_write_then_read(client, model: str, tools: list, system: list) -> tuple:
    # Call 1: cold cache -- expect a cache WRITE
    r1 = client.messages.create(
        model=model, max_tokens=100, tools=tools, system=system,
        messages=[{"role": "user", "content": "In one sentence, summarize what you can help with."}],
    )
    # Call 2: byte-identical tools+system prefix, different user message -- expect a cache READ
    r2 = client.messages.create(
        model=model, max_tokens=100, tools=tools, system=system,
        messages=[{"role": "user", "content": "In one sentence, what's the incident-listing tool called?"}],
    )
    return r1, r2
# --8<-- [end:cache-write-read]

# --8<-- [start:invalidation-hierarchy]
def tool_choice_change_vs_definition_edit(client, model: str, tools: list, system: list) -> tuple:
    # Same tools+system, but tool_choice changed -- per Anthropic's docs, this should only
    # affect the messages level; the tools+system cache read should be unaffected.
    r_tool_choice_changed = client.messages.create(
        model=model, max_tokens=100, tools=tools, system=system, tool_choice={"type": "any"},
        messages=[{"role": "user", "content": "Check the status of the billing service."}],
    )

    # One tool's description is edited by a single word -- per Anthropic's docs, this
    # invalidates the ENTIRE cache (tools, system, and messages).
    tools_modified = build_tool_library()
    tools_modified[0] = {**tools_modified[0], "description": tools_modified[0]["description"] + " (updated)"}
    tools_modified[-1]["cache_control"] = {"type": "ephemeral"}
    r_definition_edited = client.messages.create(
        model=model, max_tokens=100, tools=tools_modified, system=system,
        messages=[{"role": "user", "content": "In one sentence, what's the incident-listing tool called?"}],
    )
    return r_tool_choice_changed, r_definition_edited
# --8<-- [end:invalidation-hierarchy]

# --8<-- [start:masking-vs-removal]
MID_CONVERSATION_TOOL_CHANGES_BETA = "mid-conversation-tool-changes-2026-07-01"


def mask_a_tool(client, model: str, tools: list, system: list, tool_name: str):
    """The tools array is byte-identical to any earlier call -- masking via tool_removal,
    not editing the array, is what preserves the cache. A role:"system" message must
    precede an assistant message or end the array, so it ends this one."""
    tool_removal_directive = {"role": "system", "content": [
        {"type": "tool_removal", "tool": {"type": "tool_reference", "name": tool_name}},
    ]}
    return client.beta.messages.create(
        model=model, max_tokens=50, tools=tools, system=system,
        betas=[MID_CONVERSATION_TOOL_CHANGES_BETA],
        messages=[{"role": "user", "content": "Say OK."}, tool_removal_directive],
    )


def remove_a_tool(client, model: str, tool_name: str, system: list):
    """Contrast: physically edit the tools array (a different array than any earlier call)."""
    tools_without = build_tool_library(
        include=[n for n, _ in _FILLER_TOOL_SPECS if n != tool_name]
    )
    return client.beta.messages.create(
        model=model, max_tokens=50, tools=tools_without, system=system,
        betas=[MID_CONVERSATION_TOOL_CHANGES_BETA],
        messages=[{"role": "user", "content": "Say OK."}],
    )
# --8<-- [end:masking-vs-removal]
