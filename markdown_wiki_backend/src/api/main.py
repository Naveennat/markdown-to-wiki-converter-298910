from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import ConvertRequest, ConvertResponse, StatusResponse

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


def _md_to_wiki_stub(markdown: str) -> tuple[str, list[str]]:
    """
    Minimal, dependency-free Markdown -> wiki conversion (temporary stub).

    This function intentionally performs a *non-empty* transformation so the frontend
    preview works end-to-end until the full engine is implemented.

    Currently handled (best-effort):
    - Headings (#..######) -> (=..======)
    - Bullets (-, *, +) -> * and ordered lists (1.) -> #
    - Fenced code blocks ``` -> {{{ / }}}
    - Inline code `code` -> {{code}}
    - Links [text](url) -> [url text]
    """
    warnings: list[str] = []
    text = (markdown or "").replace("\r\n", "\n").replace("\r", "\n")

    # Convert fenced code blocks (```lang ... ```) to wiki-style block delimiters.
    out_lines: list[str] = []
    in_code = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                out_lines.append("{{{")
            else:
                in_code = False
                out_lines.append("}}}")
            continue
        out_lines.append(line)

    if in_code:
        warnings.append("Unclosed fenced code block detected; auto-closed.")
        out_lines.append("}}}")

    text = "\n".join(out_lines)

    # Headings: # H1 -> = H1 =
    def repl_heading(m: re.Match[str]) -> str:
        level = len(m.group(1))
        title = m.group(2).strip()
        eq = "=" * level
        return f"{eq} {title} {eq}"

    text = re.sub(r"^(#{1,6})\s+(.*)$", repl_heading, text, flags=re.MULTILINE)

    # Lists:
    text = re.sub(r"^(\s*)[-*+]\s+", r"\1* ", text, flags=re.MULTILINE)
    text = re.sub(r"^(\s*)\d+\.\s+", r"\1# ", text, flags=re.MULTILINE)

    # Inline code: `x` -> {{x}}
    text = re.sub(r"`([^`]+)`", r"{{\1}}", text)

    # Links: [text](url) -> [url text]
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[\2 \1]", text)

    # Ensure non-empty output formatting if input had content.
    normalized = text.strip()
    return (normalized + ("\n" if normalized else "")), warnings


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

    wiki, warnings = _md_to_wiki_stub(md)
    return ConvertResponse(wiki=wiki, warnings=warnings)
