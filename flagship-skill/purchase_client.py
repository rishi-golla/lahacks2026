"""HTTP client used by the ASI:One agent to call the Browserbase worker."""

from __future__ import annotations

import asyncio
import json
import os
from urllib import error, request

from models import PurchaseItemQuery, PurchaseItemResult


class PurchaseClientError(RuntimeError):
    pass


WORKER_URL = os.environ.get("PURCHASE_WORKER_URL", "http://127.0.0.1:8003/v1/purchase/review")
WORKER_TIMEOUT_S = float(os.environ.get("PURCHASE_WORKER_TIMEOUT_S", "120"))


async def invoke_purchase_worker(query: PurchaseItemQuery) -> PurchaseItemResult:
    return await asyncio.to_thread(_post_purchase_request, query)


def _post_purchase_request(query: PurchaseItemQuery) -> PurchaseItemResult:
    payload = json.dumps(query.model_dump(exclude_none=True)).encode("utf-8")
    req = request.Request(
        WORKER_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=WORKER_TIMEOUT_S) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PurchaseClientError(f"HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise PurchaseClientError(str(exc.reason)) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PurchaseClientError("worker returned invalid JSON") from exc
    return PurchaseItemResult.model_validate(data)
