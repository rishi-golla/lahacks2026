from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import ProductCandidate, PurchaseItemQuery, parse_purchase_query  # noqa: E402
from purchase_prompt import PURCHASE_AGENT_SYSTEM_PROMPT, render_purchase_agent_prompt  # noqa: E402
from purchase_rules import choose_candidate, ensure_price_allowed, score_candidate  # noqa: E402


def test_parse_purchase_query_accepts_json_payload() -> None:
    query = parse_purchase_query(
        '{"description":"USB-C cable","quantity":2,"brand":"Anker","max_price":20}'
    )

    assert query.description == "USB-C cable"
    assert query.quantity == 2
    assert query.brand == "Anker"
    assert query.max_price == 20


def test_parse_purchase_query_accepts_natural_language_guards() -> None:
    query = parse_purchase_query("Buy a 6ft USB-C cable qty 2 under $15")

    assert query.description == "Buy a 6ft USB-C cable qty 2 under $15"
    assert query.quantity == 2
    assert query.max_price == 15


def test_score_candidate_rewards_matching_metadata() -> None:
    query = PurchaseItemQuery(description="USB-C charging cable 6ft", brand="Anker")
    good = ProductCandidate(title="Anker USB-C Charging Cable 6ft Braided", price=9.99)
    bad = ProductCandidate(title="Wireless mouse with USB receiver", price=9.99)

    assert score_candidate(query, good) > score_candidate(query, bad)


def test_choose_candidate_returns_ambiguous_for_close_scores() -> None:
    query = PurchaseItemQuery(description="USB-C cable 6ft")
    candidates = [
        ProductCandidate(title="USB-C cable 6ft black", price=8.99),
        ProductCandidate(title="USB-C cable 6ft white", price=8.99),
    ]

    decision, selected = choose_candidate(query, candidates)

    assert decision == "ambiguous"
    assert selected is not None


def test_price_guard_blocks_total_above_max() -> None:
    query = PurchaseItemQuery(description="USB-C cable", quantity=2, max_price=10)

    try:
        ensure_price_allowed(query, 6)
    except ValueError as exc:
        assert "exceeds max_price" in str(exc)
    else:
        raise AssertionError("expected price guard to raise")


def test_purchase_prompt_contains_review_only_safety_and_result_contract() -> None:
    query = PurchaseItemQuery(description="USB-C cable", quantity=1, max_price=15)
    prompt = PURCHASE_AGENT_SYSTEM_PROMPT + "\n" + render_purchase_agent_prompt(query)

    assert "Playwright MCP" in prompt
    assert "review-only checkout" in prompt
    assert "Never place, submit, complete, confirm, or finalize an order" in prompt
    assert "needs_auth" in prompt
    assert "blocked" in prompt
    assert "ambiguous" in prompt
    assert '"status": "review_ready"' in prompt
    assert '"requires_confirmation": true' in prompt
