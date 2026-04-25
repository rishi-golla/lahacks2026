import logging

from fastapi import FastAPI

from .routers import health, session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="MetaGlassesAgent backend")
app.include_router(health.router)
app.include_router(session.router)
