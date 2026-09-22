"""
Drew Breunig names four ways context makes an agent worse -- poisoning,
distraction, confusion, clash -- and names fixes for each. Cited everywhere,
reproduced almost nowhere. This recipe builds one minimal, real repro per
failure mode, with a real fix applied and a real before/after comparison
against an independently computed ground truth.

1. Poisoning: a hallucinated fact enters context and corrupts a later
   answer. Fix: quarantine (remove/replace the bad turn before it propagates).
2. Distraction: a long run of consistent-but-wrong pattern in context pulls
   the model into repeating it instead of reasoning fresh. Fix: compress
   (drop the flawed history instead of carrying it forward).
3. Confusion: superfluous, similar-sounding tools increase the chance of
   picking the wrong one. Fix: select (only load the tools actually needed).
4. Clash: two contradictory facts sit in context at once. Fix: prune the
   stale one once a newer fact supersedes it.

No framework -- the raw Anthropic client throughout, same as the rest of
this cookbook. Run: python context_engineering.py
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
HAIKU = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


# --------------------------------------------------------- 1. Poisoning

def poisoning_demo() -> dict:
    """A hallucinated founding year enters context as a fake tool result.
    Quarantine = the bad turn is caught and replaced before the question
    that depends on it gets asked -- not just appended-to-fix, actually
    removed from history."""
    system = "You answer questions using only the information provided in this conversation."
    question = "As of 2026, how many years old is Meridian Robotics?"

    poisoned_history = [
        {"role": "user", "content": "Look up when Meridian Robotics was founded."},
        {"role": "assistant", "content": "I'll check the company database."},
        {"role": "user", "content": "[tool_result: company_lookup] Meridian Robotics was founded in 2009."},
        {"role": "assistant", "content": "Meridian Robotics was founded in 2009."},
    ]
    quarantined_history = [
        {"role": "user", "content": "Look up when Meridian Robotics was founded."},
        {"role": "assistant", "content": "I'll check the company database."},
        {"role": "user", "content": "[tool_result: company_lookup, corrected after a data error was caught] Meridian Robotics was founded in 2014."},
        {"role": "assistant", "content": "Meridian Robotics was founded in 2014."},
    ]

    poisoned = _text(client.messages.create(model=HAIKU, max_tokens=200, system=system,
                                             messages=poisoned_history + [{"role": "user", "content": question}]))
    quarantined = _text(client.messages.create(model=HAIKU, max_tokens=200, system=system,
                                                messages=quarantined_history + [{"role": "user", "content": question}]))
    return {"ground_truth_founding_year": 2014, "correct_age_2026": 12, "poisoned_answer": poisoned, "quarantined_answer": quarantined}


# --------------------------------------------------------- 2. Distraction

def distraction_demo() -> dict:
    """Six prior turns confidently apply a wrong averaging method (divide by
    N-1 instead of N). Compress = drop that flawed history and ask fresh
    instead of carrying it forward."""
    system = "Answer the arithmetic question directly."

    # Every prior "answer" divides by N-1 instead of N -- a consistent,
    # confidently-stated wrong method, not a random error.
    flawed_history = []
    examples = [([2, 4, 6], 6), ([10, 20], 30), ([3, 6, 9], 9), ([6, 6, 6, 6], 8), ([10, 10, 10, 10, 20], 15), ([50, 150], 200)]
    for nums, wrong_avg in examples:
        flawed_history.append({"role": "user", "content": f"What's the average of {', '.join(map(str, nums))}?"})
        flawed_history.append({"role": "assistant", "content": f"The average is {wrong_avg}."})

    question = "What's the average of 10, 20, 30, 40?"
    correct_average = 25  # (10+20+30+40)/4
    pattern_matched_average = 33.33  # (10+20+30+40)/3 -- what following the demonstrated N-1 pattern would give

    distracted = _text(client.messages.create(model=HAIKU, max_tokens=200, system=system,
                                               messages=flawed_history + [{"role": "user", "content": question}]))
    compressed = _text(client.messages.create(model=HAIKU, max_tokens=200, system=system,
                                               messages=[{"role": "user", "content": question}]))
    return {
        "correct_average": correct_average,
        "pattern_matched_average_if_distracted": pattern_matched_average,
        "distracted_answer": distracted,
        "compressed_answer": compressed,
    }


# --------------------------------------------------------- 3. Confusion

_CORRECT_TOOL = {
    "name": "get_live_exchange_rate",
    "description": "Get the current live exchange rate between two currencies.",
    "input_schema": {"type": "object", "properties": {"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": ["from_currency", "to_currency"]},
}
_DECOY_TOOL = {
    "name": "get_exchange_rate_estimate",
    "description": "Provides a quick estimated exchange rate based on last known cached data (may be stale).",
    "input_schema": {"type": "object", "properties": {"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": ["from_currency", "to_currency"]},
}
_FILLER_TOOLS = [
    {"name": n, "description": d, "input_schema": {"type": "object", "properties": {}}}
    for n, d in [
        ("get_currency_symbol", "Get the printable symbol for a currency code."),
        ("list_supported_currencies", "List all currency codes this system supports."),
        ("get_crypto_price", "Get the current price of a cryptocurrency."),
        ("convert_units", "Convert between measurement units like kg and lbs."),
        ("get_stock_quote", "Get the current price of a stock ticker."),
        ("get_inflation_index", "Get a country's current inflation index."),
        ("get_country_currency", "Look up which currency a country uses."),
        ("get_bank_holiday", "Check if a given date is a bank holiday."),
        ("get_tax_rate", "Get the sales tax rate for a region."),
        ("get_shipping_cost", "Estimate shipping cost between two locations."),
    ]
]
_REAL_RATE = 1.08  # EUR -> USD, fictional/illustrative
_STALE_RATE = 1.15  # what the decoy tool returns


def _exchange_impl(from_currency: str, to_currency: str) -> dict:
    return {"rate": _REAL_RATE}


def _exchange_estimate_impl(from_currency: str, to_currency: str) -> dict:
    return {"rate": _STALE_RATE}


def confusion_demo() -> dict:
    question = "How many US dollars is 200 EUR worth, using the live rate?"
    ground_truth = round(200 * _REAL_RATE, 2)

    def run(tools):
        messages = [{"role": "user", "content": question}]
        impls = {"get_live_exchange_rate": _exchange_impl, "get_exchange_rate_estimate": _exchange_estimate_impl}
        for _ in range(4):
            response = client.messages.create(model=HAIKU, max_tokens=300, tools=tools, messages=messages)
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                return {"answer": _text(response), "tool_called": None}
            block = next(b for b in response.content if b.type == "tool_use")
            result = impls.get(block.name, lambda **_: {"error": "not implemented in this demo"})(**block.input)
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}]})
            if block.name in impls:
                final = client.messages.create(model=HAIKU, max_tokens=200, tools=tools, messages=messages)
                return {"answer": _text(final), "tool_called": block.name}
        return {"answer": "(budget exhausted)", "tool_called": None}

    clean = run([_CORRECT_TOOL])
    confused = run([_CORRECT_TOOL, _DECOY_TOOL] + _FILLER_TOOLS)
    return {"ground_truth_usd": ground_truth, "clean_result": clean, "confused_result": confused, "tool_count_confused": 2 + len(_FILLER_TOOLS)}


# --------------------------------------------------------- 4. Clash

def clash_demo() -> dict:
    """Two contradictory refund-window facts in context at once. Fix =
    prune the stale one once a newer, superseding fact is known."""
    system = "You answer questions using only the information provided in this conversation."
    question = "What is the refund window, in days?"

    clashing_history = [
        {"role": "user", "content": "[policy_doc v1, published Jan 2026] The refund window is 30 days."},
        {"role": "user", "content": "[policy_doc v2, published Aug 2026, supersedes v1] The refund window is 14 days."},
    ]
    pruned_history = [
        {"role": "user", "content": "[policy_doc v2, published Aug 2026, current policy] The refund window is 14 days."},
    ]

    clashing = _text(client.messages.create(model=HAIKU, max_tokens=200, system=system,
                                             messages=clashing_history + [{"role": "user", "content": question}]))
    pruned = _text(client.messages.create(model=HAIKU, max_tokens=200, system=system,
                                           messages=pruned_history + [{"role": "user", "content": question}]))
    return {"ground_truth_days": 14, "clashing_answer": clashing, "pruned_answer": pruned}


def main() -> None:
    print("=" * 70); print("1. POISONING (fix: quarantine)"); print("=" * 70)
    print(json.dumps(poisoning_demo(), indent=2))

    print(); print("=" * 70); print("2. DISTRACTION (fix: compress)"); print("=" * 70)
    print(json.dumps(distraction_demo(), indent=2))

    print(); print("=" * 70); print("3. CONFUSION (fix: select)"); print("=" * 70)
    print(json.dumps(confusion_demo(), indent=2))

    print(); print("=" * 70); print("4. CLASH (fix: prune)"); print("=" * 70)
    print(json.dumps(clash_demo(), indent=2))


if __name__ == "__main__":
    main()
