import logging
from pathlib import Path

from dotenv import load_dotenv

# Load all of `backend/.env` into the process environment so bridge flags and
# secrets apply to modules that read `os.environ` (not only Pydantic settings).
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

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
