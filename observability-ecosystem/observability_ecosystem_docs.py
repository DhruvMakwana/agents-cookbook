"""
Same logic as observability_ecosystem.py, split into self-contained
blocks for blog embedding via pymdownx.snippets.
"""

# --8<-- [start:trace-payload]
import json


def build_otel_genai_trace() -> dict:
    """The same real gen_ai.* attribute shape the Observability and Debugging
    recipe's own trace uses -- built here as a real OTLP/HTTP JSON export
    payload, the format Langfuse's own docs specify for its OTLP endpoint."""
    return {
        "resourceSpans": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "loopline-support-agent"}}]},
            "scopeSpans": [{
                "scope": {"name": "agents-cookbook.observability-ecosystem"},
                "spans": [{
                    "name": "execute_tool get_daily_active_users",
                    "attributes": [
                        {"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
                        {"key": "gen_ai.tool.name", "value": {"stringValue": "get_daily_active_users"}},
                        {"key": "gen_ai.provider.name", "value": {"stringValue": "anthropic"}},
                        {"key": "gen_ai.input.messages", "value": {"stringValue": json.dumps({"product": "Nimbus"})}},
                        {"key": "gen_ai.output.messages", "value": {"stringValue": json.dumps({"daily_active_users": 2340000})}},
                    ],
                }],
            }],
        }],
    }
# --8<-- [end:trace-payload]

# --8<-- [start:live-checks]
import requests


def check_langfuse_otlp_endpoint() -> dict:
    """Real, live POST to Langfuse's real, documented OTLP ingestion endpoint,
    with no credentials. No account needed -- this tests the endpoint's real,
    documented behavior, not a mocked one."""
    trace = build_otel_genai_trace()
    response = requests.post(
        "https://cloud.langfuse.com/api/public/otel/v1/traces",
        json=trace, headers={"Content-Type": "application/json"}, timeout=15,
    )
    return {"status_code": response.status_code, "real_response_body": response.json()}


def check_helicone_gateway_no_target() -> dict:
    """Real, live POST to Helicone's real gateway with no target header --
    tests whether it's an ingestion sink or a request-path proxy."""
    response = requests.post(
        "https://gateway.helicone.ai/v1/chat/completions",
        json={}, headers={"Content-Type": "application/json"}, timeout=15,
    )
    return {"status_code": response.status_code, "real_response_body": response.text}


def check_helicone_gateway_with_target() -> dict:
    """Real, live POST to Helicone's real gateway with a real target header
    pointing at a real upstream provider -- confirms live forwarding."""
    response = requests.post(
        "https://gateway.helicone.ai/v1/chat/completions",
        json={"model": "gpt-4", "messages": []},
        headers={"Content-Type": "application/json", "Helicone-Target-Url": "https://api.openai.com"},
        timeout=15,
    )
    return {"status_code": response.status_code, "real_response_body": response.json()}
# --8<-- [end:live-checks]
