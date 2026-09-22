"""
Pluggable LLM providers, shared across every recipe in this cookbook.

Pick a provider with the LLM_PROVIDER env var: "anthropic" | "openai" | "ollama".
Default provider is Anthropic. Credentials are read from a .env file --
python-dotenv walks up from this file's directory to find the nearest one,
so a single .env at the cookbook root (agents-cookbook/.env) covers every
recipe; a recipe can still override with its own local .env.

Model choice is task-scaled, not one-size-fits-all: pass model="claude-haiku-4-5"
for simple classification/judgment calls and model="claude-sonnet-5" for
anything needing real reasoning. ANTHROPIC_MODEL in .env is only the
fallback when a call doesn't specify one -- it defaults to the cheap tier.

This file is duplicated into each recipe folder (not imported across folders)
so every recipe stays self-contained and pip-installable on its own -- copy
the current version from here when adding a new recipe, don't symlink it.
"""

import os

# --8<-- [start:provider_dispatch]
def generate(prompt: str, provider: str | None = None, model: str | None = None) -> str:
    """Route to the configured LLM provider and return its text response."""
    provider = (provider or os.environ.get("LLM_PROVIDER", "anthropic")).lower()

    if provider == "anthropic":
        return _generate_anthropic(prompt, model or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5"))
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
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to agents-cookbook/.env.")

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
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to agents-cookbook/.env.")

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
    # model/version). Leaving `think` at its default keeps `content` clean
    # and routes reasoning to a separate `message["thinking"]` field, which
    # this wrapper discards.
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]
# --8<-- [end:provider_ollama]
