"""FastAPI worker that runs the Browserbase purchase automation."""

from __future__ import annotations

import os

from fastapi import FastAPI

from browserbase_purchase import prepare_purchase_review
from models import PurchaseItemQuery, PurchaseItemResult


app = FastAPI(title="Browserbase Purchase Worker", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/purchase/review", response_model=PurchaseItemResult)
async def purchase_review(query: PurchaseItemQuery) -> PurchaseItemResult:
    return await prepare_purchase_review(query)


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PURCHASE_WORKER_PORT", "8003"))
    uvicorn.run("browserbase_worker:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()

