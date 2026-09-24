"""
A real repro of a specific failure mode Anthropic's own engineering blog
documents for multi-agent research systems: subagents "performed the
exact same searches as other agents... without an effective division of
labor" -- and their own prescribed fix: give each subagent "an
objective, an output format, guidance on the tools and sources to use,
and clear task boundaries."

A fixed, fictional 6-document corpus on a single broad research topic
(remote work policy), searchable by 3 real subagents under two
conditions:

  - vague: all 3 subagents get the identical, generic instruction --
    no assigned scope, no boundaries.
  - scoped: each of the 3 subagents gets a distinct, explicitly-bounded
    objective covering a different third of the topic -- Anthropic's
    own prescribed fix, applied literally.

Real measurement: how much real document-retrieval OVERLAP occurs
between the 3 subagents under each condition.

Run: python deep_research_agents.py
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SONNET = "claude-sonnet-5"

# ------------------------------------------------------- A fixed, fictional 6-document corpus

_DOCUMENTS = {
    "productivity-study": {
        "content": "A 2024 internal study found individual contributor output metrics were roughly flat for remote employees versus office-based peers, with more variance by role than by location.",
        "keywords": {"productivity", "output", "performance", "metrics"},
    },
    "real-estate-costs": {
        "content": "Moving to a hybrid model reduced office square footage needs by 40%, cutting annual real estate and utility overhead substantially.",
        "keywords": {"cost", "costs", "expense", "budget", "estate", "overhead", "savings"},
    },
    "culture-collaboration": {
        "content": "Manager surveys reported spontaneous cross-team collaboration and informal mentorship dropped noticeably in fully remote teams compared to in-office teams.",
        "keywords": {"culture", "collaboration", "mentorship", "cohesion"},
    },
    "retention-flexibility": {
        "content": "Exit interviews cited flexible remote work as a top-3 reason employees stayed longer than their original planned tenure.",
        "keywords": {"retention", "flexibility", "turnover", "tenure", "attrition"},
    },
    "security-endpoints": {
        "content": "Distributed home-office setups increased the number of unmanaged network endpoints, raising the attack surface tracked by the security team.",
        "keywords": {"security", "endpoints", "risk", "attack", "breach", "vpn"},
    },
    "commute-environment": {
        "content": "Eliminating daily commutes for remote staff was estimated to reduce the company's commute-related carbon footprint by a measurable amount per employee per year.",
        "keywords": {"commute", "commuting", "environment", "environmental", "carbon", "emissions"},
    },
}

_SEARCH_TOOL = [{
    "name": "search_documents",
    "description": "Search the internal document corpus for information relevant to a query. Returns matching document IDs and their content.",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}]

_VAGUE_PROMPT = "Research remote work policy for a company evaluating whether to keep it. Use the search_documents tool to find relevant information, then summarize your findings in 2-3 sentences."

_SCOPED_PROMPTS = [
    "You are researching ONLY the productivity and real-estate/cost impacts of remote work policy. Do not research culture, retention, security, or environmental impacts -- another subagent covers those. Use search_documents, then summarize your findings in 2-3 sentences, scoped strictly to your assigned area.",
    "You are researching ONLY the culture/collaboration and employee-retention impacts of remote work policy. Do not research productivity, cost, security, or environmental impacts -- another subagent covers those. Use search_documents, then summarize your findings in 2-3 sentences, scoped strictly to your assigned area.",
    "You are researching ONLY the security and environmental/commute impacts of remote work policy. Do not research productivity, cost, culture, or retention -- another subagent covers those. Use search_documents, then summarize your findings in 2-3 sentences, scoped strictly to your assigned area.",
]


import re


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z]+", text.lower()))


def _keyword_match(query: str) -> list:
    """A simple, deterministic real search over the fixed corpus -- matches on each
    document's own curated keyword set (a real, explicit topic index), not raw prose
    overlap, to avoid generic connector words (e.g. 'employee', 'team') producing
    false-positive matches across unrelated documents. No LLM judgment involved in
    retrieval itself, only in which query terms a subagent chooses to use."""
    query_tokens = _tokenize(query)
    hits = []
    for doc_id, doc in _DOCUMENTS.items():
        if query_tokens & doc["keywords"]:
            hits.append(doc_id)
    return hits


def _run_subagent(prompt: str) -> dict:
    messages = [{"role": "user", "content": prompt}]
    docs_retrieved = set()

    for _ in range(4):
        response = client.messages.create(model=SONNET, max_tokens=400, tools=_SEARCH_TOOL, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            final_text = "\n".join(b.text for b in response.content if b.type == "text")
            return {"docs_retrieved": sorted(docs_retrieved), "summary": final_text}
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            hits = _keyword_match(block.input["query"])
            docs_retrieved.update(hits)
            content = "\n".join(f"[{d}] {_DOCUMENTS[d]['content']}" for d in hits) if hits else "No matching documents."
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
        messages.append({"role": "user", "content": tool_results})

    return {"docs_retrieved": sorted(docs_retrieved), "summary": None}


def _overlap_stats(subagent_results: list) -> dict:
    doc_sets = [set(r["docs_retrieved"]) for r in subagent_results]
    all_retrieved = set().union(*doc_sets) if doc_sets else set()
    retrieved_by_multiple = {d for d in all_retrieved if sum(d in s for s in doc_sets) > 1}
    total_retrievals = sum(len(s) for s in doc_sets)
    return {
        "unique_docs_covered": len(all_retrieved),
        "docs_retrieved_by_more_than_one_subagent": sorted(retrieved_by_multiple),
        "redundant_retrieval_count": total_retrievals - len(all_retrieved),
        "total_retrievals": total_retrievals,
    }


def division_of_labor_demo() -> dict:
    vague_results = [_run_subagent(_VAGUE_PROMPT) for _ in range(3)]
    scoped_results = [_run_subagent(p) for p in _SCOPED_PROMPTS]
    return {
        "vague": {"subagents": vague_results, "overlap": _overlap_stats(vague_results)},
        "scoped": {"subagents": scoped_results, "overlap": _overlap_stats(scoped_results)},
    }


def main() -> None:
    print("=" * 70)
    print("Real repro: subagent division of labor -- vague vs. scoped instructions")
    print("=" * 70)
    print(json.dumps(division_of_labor_demo(), indent=2))


if __name__ == "__main__":
    main()
