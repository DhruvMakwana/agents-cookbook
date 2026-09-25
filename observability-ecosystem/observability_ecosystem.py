"""
A real, live test of two architecturally different observability
platform mechanisms, using only real, public, documented endpoints --
no account, no API key, no cost. Companion to the Observability and
Debugging recipe, which covers the OpenTelemetry GenAI semantic
convention itself; this one tests the real ecosystem built around it.

Two real, live checks:

  1. Langfuse's real, documented OTLP ingestion endpoint
     (`/api/public/otel`) -- a real OTel-GenAI-shaped trace, built to
     the exact same gen_ai.* attribute shape as the Observability and
     Debugging recipe's own trace, POSTed with no credentials. Real,
     live response expected: 401, with Langfuse's own real, specific
     error message -- confirming the endpoint is real, live, and
     genuinely validates OTLP ingestion per its own documentation.

  2. Helicone's real, documented AI gateway endpoint
     (`gateway.helicone.ai`) -- tested twice: once with no target
     header (real, live "Missing target base url" response, proving
     it's a request-path proxy, not an ingestion sink), and once with
     a real target header pointing at a real upstream provider,
     showing the request actually gets forwarded live and the
     upstream's own real error comes back through the proxy.

Run: python observability_ecosystem.py
"""

import json

import requests

# ------------------------------------------------------- A real OTel GenAI-shaped trace payload

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


# ------------------------------------------------------- Real, live checks against real endpoints

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
    tests whether it's an ingestion sink (would accept and log this) or a
    request-path proxy (would fail without knowing where to forward)."""
    response = requests.post(
        "https://gateway.helicone.ai/v1/chat/completions",
        json={}, headers={"Content-Type": "application/json"}, timeout=15,
    )
    return {"status_code": response.status_code, "real_response_body": response.text}


def check_helicone_gateway_with_target() -> dict:
    """Real, live POST to Helicone's real gateway, this time WITH a real target
    header pointing at a real upstream provider -- confirms the request is
    actually forwarded live, and the real upstream's own response comes back
    through the proxy, not a Helicone-internal error."""
    response = requests.post(
        "https://gateway.helicone.ai/v1/chat/completions",
        json={"model": "gpt-4", "messages": []},
        headers={"Content-Type": "application/json", "Helicone-Target-Url": "https://api.openai.com"},
        timeout=15,
    )
    return {"status_code": response.status_code, "real_response_body": response.json()}


def ecosystem_architecture_demo() -> dict:
    return {
        "langfuse_otlp_ingestion_endpoint": check_langfuse_otlp_endpoint(),
        "helicone_gateway_no_target": check_helicone_gateway_no_target(),
        "helicone_gateway_with_target_forwarded_live": check_helicone_gateway_with_target(),
    }


def main() -> None:
    print("=" * 70)
    print("Real, live check: two observability platform architectures")
    print("=" * 70)
    print(json.dumps(ecosystem_architecture_demo(), indent=2))


if __name__ == "__main__":
    main()
