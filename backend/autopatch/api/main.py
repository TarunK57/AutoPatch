"""FastAPI Application Entry Point for AutoPatch."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autopatch.api.routes import router

app = FastAPI(
    title="AutoPatch API",
    version="1.0.0",
    description=(
        "Autonomous bug detection and repair product API. "
        "Uploads code projects, finds flaws, reproduces bugs with executable tests (BRT), "
        "generates minimal patches, verifies them in ephemeral Docker sandboxes, "
        "and requires explicit human approval before patch application."
    ),
    openapi_tags=[
        {
            "name": "AutoPatch API",
            "description": "Endpoints for project management, scanning, bug repair, and human review.",
        }
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for Next.js frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Service health and uptime endpoint."""
    return {"status": "ok", "service": "AutoPatch", "version": "1.0.0"}
