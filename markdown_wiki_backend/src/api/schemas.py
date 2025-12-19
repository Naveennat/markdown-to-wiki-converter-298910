from typing import List, Optional

from pydantic import BaseModel, Field


class ConvertRequest(BaseModel):
    """Request body for markdown-to-wiki conversion."""

    markdown: str = Field(..., description="Markdown source to convert.")


class ConvertResponse(BaseModel):
    """Response body containing the converted wiki output and optional warnings."""

    wiki: str = Field(..., description="Converted wiki output.")
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal conversion warnings (best-effort conversion notes).",
    )


class StatusResponse(BaseModel):
    """Service status/metadata response."""

    status: str = Field(..., description="Overall service status.")
    service: str = Field(..., description="Service identifier.")
    version: str = Field(..., description="Service version string.")
    supported_features: List[str] = Field(
        default_factory=list,
        description="List of supported conversion feature names/keywords.",
    )
    time: Optional[str] = Field(
        default=None,
        description="Server UTC time in ISO 8601 format (optional).",
    )
