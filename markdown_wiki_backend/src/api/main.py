from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import ConvertRequest, ConvertResponse, StatusResponse
from src.converter.engine import convert as md_to_wiki_convert

SERVICE_NAME = "markdown_wiki_backend"
VERSION = "0.1.0"

# A temporary feature list so the frontend can display capabilities even before the
# full conversion engine is implemented.
SUPPORTED_FEATURES: list[str] = [
    "headings",
    "unordered_lists",
    "ordered_lists",
    "fenced_code_blocks",
    "inline_code",
    "links",
]

openapi_tags = [
    {"name": "meta", "description": "Service metadata/health endpoints."},
    {"name": "convert", "description": "Markdown to wiki conversion endpoints."},
]

app = FastAPI(
    title="Markdown Wiki Backend",
    description="Backend API for converting Markdown content into a wiki-style markup.",
    version=VERSION,
    openapi_tags=openapi_tags,
)

# Permissive CORS for local dev + preview environments.
# (Requirement: keep this permissive.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





@app.get(
    "/",
    tags=["meta"],
    summary="Root (compatibility)",
    description="Compatibility root endpoint; kept for existing clients.",
    operation_id="root_get",
)
# PUBLIC_INTERFACE
def root() -> dict[str, str]:
    """Compatibility root endpoint; returns a basic service message."""
    return {"message": "Healthy"}


@app.get(
    "/health",
    tags=["meta"],
    summary="Health check",
    description='Simple health endpoint. Returns 200 with {"status":"ok"}.',
    operation_id="health_get",
)
# PUBLIC_INTERFACE
def health() -> dict[str, Any]:
    """Return a minimal health response used for uptime checks."""
    return {"status": "ok"}


@app.get(
    "/status",
    tags=["meta"],
    summary="Service status/metadata",
    description="Returns version and a list of supported conversion features.",
    response_model=StatusResponse,
    operation_id="status_get",
)
# PUBLIC_INTERFACE
def status() -> StatusResponse:
    """Return service metadata including version and supported feature list."""
    return StatusResponse(
        status="ok",
        service=SERVICE_NAME,
        version=VERSION,
        supported_features=SUPPORTED_FEATURES,
        time=datetime.now(timezone.utc).isoformat(),
    )


@app.post(
    "/convert",
    tags=["convert"],
    summary="Convert Markdown to wiki format",
    description="Accepts Markdown input and returns wiki-format output with optional warnings.",
    response_model=ConvertResponse,
    operation_id="convert_post",
)
# PUBLIC_INTERFACE
def convert(req: ConvertRequest) -> ConvertResponse:
    """
    Convert Markdown text into wiki-format markup.

    Parameters:
        req: ConvertRequest containing the Markdown source.

    Returns:
        ConvertResponse with the converted wiki text and optional warnings.
    """
    md = (req.markdown or "").strip()
    if not md:
        raise HTTPException(status_code=400, detail="markdown is required")

    wiki, warnings = md_to_wiki_convert(md)
    return ConvertResponse(wiki=wiki, warnings=warnings)
