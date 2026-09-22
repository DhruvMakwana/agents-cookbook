"""
Pluggable LLM providers, shared across every recipe in this cookbook.

Pick a provider with the LLM_PROVIDER env var: "anthropic" | "openai" | "ollama".
Anthropic and OpenAI need an API key (read from .env, never logged or printed).
Ollama runs fully locally and needs no key at all -- default here, since it's
the provider actually verified in this repo (no paid keys were available when
these recipes were built and run; see each recipe's README for what was
actually exercised versus what is supported but unexercised).

This file is duplicated into each recipe folder (not imported across folders)
so every recipe stays self-contained and pip-installable on its own -- copy
the current version from here when adding a new recipe, don't symlink it.
"""

import os

# --8<-- [start:provider_dispatch]
def generate(prompt: str, provider: str | None = None, model: str | None = None) -> str:
    """Route to the configured LLM provider and return its text response."""
    provider = (provider or os.environ.get("LLM_PROVIDER", "ollama")).lower()

    if provider == "anthropic":
        return _generate_anthropic(prompt, model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-5"))
    if provider == "openai":
        # Default model id is unverified -- see .env.example.
        return _generate_openai(prompt, model or os.environ.get("OPENAI_MODEL", "gpt-5.1"))
    if provider == "ollama":
        return _generate_ollama(prompt, model or os.environ.get("OLLAMA_MODEL", "qwen3:4b"))

    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Use 'anthropic', 'openai', or 'ollama'.")
# --8<-- [end:provider_dispatch]


# --8<-- [start:provider_anthropic]
def _generate_anthropic(prompt: str, model: str) -> str:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
# --8<-- [end:provider_anthropic]


# --8<-- [start:provider_openai]
def _generate_openai(prompt: str, model: str) -> str:
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(model=model, input=prompt)
    return response.output_text
# --8<-- [end:provider_openai]


# --8<-- [start:provider_ollama]
def _generate_ollama(prompt: str, model: str) -> str:
    import ollama

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    client = ollama.Client(host=host)
    # Deliberately do NOT pass think=False here: for qwen3 models that is a
    # documented Ollama quirk where reasoning text leaks INTO the `content`
    # field instead of being suppressed (verified directly against this
    # model/version below, not assumed). Leaving `think` at its default
    # keeps `content` clean and routes reasoning to a separate
    # `message["thinking"]` field, which this wrapper discards.
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]
# --8<-- [end:provider_ollama]
