from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Markdown Wiki Backend", version="0.1.0")

# Permissive CORS for local dev + preview environments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConvertRequest(BaseModel):
    markdown: str = Field(..., description="Markdown source to convert.")


class ConvertResponse(BaseModel):
    wiki: str = Field(..., description="Converted wiki output.")
    warnings: list[str] = Field(default_factory=list)


def _md_to_wiki(markdown: str) -> tuple[str, list[str]]:
    """
    Minimal, dependency-free markdown -> wiki conversion.

    This is intentionally simple but covers common cases:
    - Headings (#..######) -> (=..======)
    - Bullets (-, *, +) and numbered lists -> * / #
    - Fenced code blocks ```lang -> {{{
    - Inline code `code` -> {{code}}
    - Links [text](url) -> [url text]
    """
    warnings: list[str] = []
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")

    # Convert fenced code blocks
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
    # - item / * item / + item -> * item
    text = re.sub(r"^(\s*)[-*+]\s+", r"\1* ", text, flags=re.MULTILINE)
    # 1. item -> # item
    text = re.sub(r"^(\s*)\d+\.\s+", r"\1# ", text, flags=re.MULTILINE)

    # Inline code: `x` -> {{x}}
    text = re.sub(r"`([^`]+)`", r"{{\1}}", text)

    # Links: [text](url) -> [url text]
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[\2 \1]", text)

    return text.strip() + ("\n" if text.strip() else ""), warnings


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Healthy"}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/status")
def status() -> dict[str, Any]:
    return {"status": "ok", "service": "markdown_wiki_backend", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/convert", response_model=ConvertResponse)
def convert(req: ConvertRequest) -> ConvertResponse:
    md = (req.markdown or "").strip()
    if not md:
        raise HTTPException(status_code=400, detail="markdown is required")

    wiki, warnings = _md_to_wiki(md)
    return ConvertResponse(wiki=wiki, warnings=warnings)
