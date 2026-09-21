"""FastAPI application entrypoint.

Vercel looks for a FastAPI instance named `app` at a supported entrypoint;
`app/main.py` is one of them, so no `tool.vercel.entrypoint` override is needed.
"""

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import VERSION, get_settings
from app.routers import health
from app.security import ACCESS_CODE_HEADER, require_access_code

# Log timings, sizes, counts and error types only — never transcript content
# and never key material (Hard Rules 4 and 5).
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

settings = get_settings()

app = FastAPI(
    title="StatusPilot API",
    version=VERSION,
    description=(
        "Turns a meeting transcript into MoM, action items, "
        "a RAID log, and a status report."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", ACCESS_CODE_HEADER],
    expose_headers=["Content-Disposition"],
)

# /api/health is intentionally unauthenticated so a deploy can be verified from a
# phone before the access code is known.
app.include_router(health.router)

# Routers added from Phase 2 onward all carry the access-code dependency.
PROTECTED = [Depends(require_access_code)]
