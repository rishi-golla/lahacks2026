"""Deterministic purchase helper rules shared by tests and prompt setup."""

from __future__ import annotations

import os
import re

from models import ProductCandidate, PurchaseItemQuery


DEFAULT_MAX_TOTAL = os.environ.get("PURCHASE_MAX_TOTAL_USD")
AMBIGUOUS_SCORE_DELTA = 0.08
MIN_ACCEPT_SCORE = 0.34


def build_search_terms(query: PurchaseItemQuery) -> str:
    parts = [
        query.brand,
        query.model,
        query.description,
        query.variant,
        query.size,
        query.color,
        *query.required_features,
    ]
    return " ".join(part for part in parts if part)


def score_candidate(query: PurchaseItemQuery, candidate: ProductCandidate) -> float:
    haystack = _tokens(candidate.title)
    if not haystack:
        return 0.0

    wanted_text = " ".join(
        part
        for part in [
            query.description,
            query.brand or "",
            query.model or "",
            query.variant or "",
            query.size or "",
            query.color or "",
            " ".join(query.required_features),
        ]
        if part
    )
    wanted = _tokens(wanted_text)
    overlap = len(wanted & haystack) / max(len(wanted), 1)

    bonus = 0.0
    for exact in (query.brand, query.model, query.variant, query.size, query.color):
        if exact and exact.lower() in candidate.title.lower():
            bonus += 0.08
    if candidate.price is not None:
        max_price = effective_max_price(query)
        if max_price is not None and candidate.price <= max_price:
            bonus += 0.05

    return min(overlap + bonus, 1.0)


def choose_candidate(query: PurchaseItemQuery, candidates: list[ProductCandidate]) -> tuple[str, ProductCandidate | None]:
    if not candidates:
        return "not_found", None

    scored = []
    for candidate in candidates:
        candidate.score = score_candidate(query, candidate)
        scored.append(candidate)
    scored.sort(key=lambda item: item.score, reverse=True)

    best = scored[0]
    if best.score < MIN_ACCEPT_SCORE:
        return "not_found", None
    if len(scored) > 1 and (best.score - scored[1].score) < AMBIGUOUS_SCORE_DELTA:
        return "ambiguous", best
    return "selected", best


def effective_max_price(query: PurchaseItemQuery) -> float | None:
    if query.max_price is not None:
        return query.max_price
    if DEFAULT_MAX_TOTAL:
        try:
            return float(DEFAULT_MAX_TOTAL)
        except ValueError:
            return None
    return None


def ensure_price_allowed(query: PurchaseItemQuery, price: float | None) -> None:
    max_price = effective_max_price(query)
    if max_price is None or price is None:
        return
    if price * query.quantity > max_price:
        raise ValueError(f"price {price * query.quantity:.2f} exceeds max_price {max_price:.2f}")


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"(\d+(?:,\d{3})*(?:\.\d{2})?)", text)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def _tokens(text: str) -> set[str]:
    ignored = {"the", "a", "an", "and", "or", "for", "with", "of", "to", "in", "on"}
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in ignored}
