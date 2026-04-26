import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load all of `backend/.env` into the process environment so bridge flags and
# secrets apply to modules that read `os.environ` (not only Pydantic settings).
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from .routers import google, health, omegaclaw_bridge, session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="MetaGlassesAgent backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(google.router)
app.include_router(session.router)
app.include_router(omegaclaw_bridge.router, prefix="/internal/omegaclaw")
