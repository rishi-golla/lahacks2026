"""Typed request and result models for the local Playwright MCP purchase agent."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


PurchaseStatus = Literal["review_ready", "needs_auth", "not_found", "ambiguous", "blocked", "error"]
ProductSearchStatus = Literal["products_ready", "needs_auth", "blocked", "error"]
Confidence = Literal["high", "medium", "low"]


class PurchaseItemQuery(BaseModel):
    description: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1, le=20)
    brand: str | None = None
    model: str | None = None
    variant: str | None = None
    size: str | None = None
    color: str | None = None
    max_price: float | None = Field(default=None, ge=0)
    required_features: list[str] = Field(default_factory=list)
    disallow_substitutes: bool = True

    @field_validator("description", "brand", "model", "variant", "size", "color", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("description")
    @classmethod
    def require_description(cls, value: str | None) -> str:
        if not value:
            raise ValueError("description is required")
        return value


class ProductCandidate(BaseModel):
    title: str
    url: str | None = None
    price: float | None = None
    price_text: str | None = None
    availability: str | None = None
    score: float = 0.0


class PurchaseItemResult(BaseModel):
    status: PurchaseStatus
    summary: str
    confidence: Confidence = "low"
    requires_confirmation: bool = True
    product_title: str | None = None
    product_url: str | None = None
    price: str | float | None = None
    quantity: int = 1
    checkout_url: str | None = None
    automation_session_id: str | None = None
    browser_profile: str | None = None
    candidates: list[ProductCandidate] = Field(default_factory=list)
    error: str | None = None


class ProductSearchResult(BaseModel):
    status: ProductSearchStatus
    summary: str
    confidence: Confidence = "low"
    quantity: int = 1
    search_url: str | None = None
    automation_session_id: str | None = None
    browser_profile: str | None = None
    candidates: list[ProductCandidate] = Field(default_factory=list)
    error: str | None = None


_QUANTITY_RE = re.compile(r"\b(?:qty|quantity)\s*[:=]?\s*(\d{1,2})\b", re.IGNORECASE)
_MAX_PRICE_RE = re.compile(r"\b(?:under|below|max(?:imum)?(?: price)?|less than)\s*\$?(\d+(?:\.\d{1,2})?)\b", re.IGNORECASE)


def parse_purchase_query(text: str) -> PurchaseItemQuery:
    """Parse either JSON product metadata or a natural-language description."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("empty purchase request")

    data = _try_json_object(cleaned)
    if data is None:
        data = _parse_natural_language(cleaned)
    return PurchaseItemQuery.model_validate(data)


def _try_json_object(text: str) -> dict[str, Any] | None:
    candidate = text
    if "```" in text:
        chunks = [chunk.strip() for chunk in text.split("```") if chunk.strip()]
        for chunk in chunks:
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            parsed = _loads_object(chunk)
            if parsed is not None:
                return parsed
    return _loads_object(candidate)


def _loads_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        raise ValueError("purchase request JSON must be an object")
    return parsed


def _parse_natural_language(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {"description": text}
    quantity = _QUANTITY_RE.search(text)
    if quantity:
        data["quantity"] = int(quantity.group(1))
    max_price = _MAX_PRICE_RE.search(text)
    if max_price:
        data["max_price"] = float(max_price.group(1))
    return data
