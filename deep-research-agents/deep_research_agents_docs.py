"""
Same logic as deep_research_agents.py, split into self-contained blocks
for blog embedding via pymdownx.snippets.
"""

# --8<-- [start:corpus-and-search]
import re

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


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z]+", text.lower()))


def _keyword_match(query: str) -> list:
    """A simple, deterministic real search over the fixed corpus -- matches on each
    document's own curated keyword set (a real, explicit topic index), not raw prose
    overlap, to avoid generic connector words producing false-positive matches."""
    query_tokens = _tokenize(query)
    return [doc_id for doc_id, doc in _DOCUMENTS.items() if query_tokens & doc["keywords"]]
# --8<-- [end:corpus-and-search]

# --8<-- [start:vague-vs-scoped]
_VAGUE_PROMPT = "Research remote work policy for a company evaluating whether to keep it. Use the search_documents tool to find relevant information, then summarize your findings in 2-3 sentences."

_SCOPED_PROMPTS = [
    "You are researching ONLY the productivity and real-estate/cost impacts of remote work policy. Do not research culture, retention, security, or environmental impacts -- another subagent covers those. Use search_documents, then summarize your findings in 2-3 sentences, scoped strictly to your assigned area.",
    "You are researching ONLY the culture/collaboration and employee-retention impacts of remote work policy. Do not research productivity, cost, security, or environmental impacts -- another subagent covers those. Use search_documents, then summarize your findings in 2-3 sentences, scoped strictly to your assigned area.",
    "You are researching ONLY the security and environmental/commute impacts of remote work policy. Do not research productivity, cost, culture, or retention -- another subagent covers those. Use search_documents, then summarize your findings in 2-3 sentences, scoped strictly to your assigned area.",
]
# --8<-- [end:vague-vs-scoped]

# --8<-- [start:overlap-stats]
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
# --8<-- [end:overlap-stats]
