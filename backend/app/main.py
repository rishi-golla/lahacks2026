import logging

from fastapi import FastAPI

from .routers import health, omegaclaw_bridge, session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="MetaGlassesAgent backend")
app.include_router(health.router)
app.include_router(session.router)
app.include_router(omegaclaw_bridge.router, prefix="/internal/omegaclaw")
