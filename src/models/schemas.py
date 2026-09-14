"""
Data contracts and strict schemas for Trend Intelligence Engine pipelines.
Enforces validation and serialization across collectors, analyzers, and exporters using Pydantic v2.
"""

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class VideoMetadata(BaseModel):
    """Normalized video metadata extracted from social media and video platforms."""
    video_id: str = Field(..., min_length=1, description="Unique video identifier")
    title: str = Field(..., min_length=1, description="Video publication title")
    channel_title: str = Field(default="", description="Channel or creator name")
    view_count: int = Field(default=0, ge=0, description="Total recorded view count")
    like_count: int = Field(default=0, ge=0, description="Total likes count")
    comment_count: int = Field(default=0, ge=0, description="Total comments count")
    published_at: datetime | None = Field(default=None, description="Publication timestamp")
    subtopic_id: str = Field(default="geral", description="Associated topic or category tag")
    video_url: str = Field(..., description="Canonical URL to the video")

    @field_validator("video_url")
    @classmethod
    def validate_video_url(cls, v: str) -> str:
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("Video URL must be a valid HTTP or HTTPS address.")
        return v


class CommentPayload(BaseModel):
    """Individual social comment extracted for high-throughput sentiment processing."""
    comment_id: str = Field(..., min_length=1, description="Unique comment identifier")
    video_id: str = Field(..., min_length=1, description="Associated parent video identifier")
    author: str = Field(default="Anonymous", description="Comment author username")
    text: str = Field(..., min_length=1, description="Raw comment text body")
    like_count: int = Field(default=0, ge=0, description="Comment like counter")
    published_at: datetime | None = Field(default=None, description="Comment publication timestamp")


class SentimentAnalysisResult(BaseModel):
    """Structured AI output summarizing sentiment, key pain points, and topics."""
    sentiment: Literal["Positivo", "Negativo", "Neutro", "Inconclusivo"] = Field(
        default="Inconclusivo",
        description="Categorized audience sentiment"
    )
    summary: str = Field(..., min_length=5, description="Executive narrative summary of audience reception")
    pain_points: list[str] = Field(
        default_factory=list,
        description="Extracted customer frustrations, questions, or product complaints"
    )
    key_takeaways: list[str] = Field(
        default_factory=list,
        description="High-level insights or actionable takeaways"
    )
    confidence_score: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence level of the LLM extraction (0.0 to 1.0)"
    )


class MondayItemPayload(BaseModel):
    """Payload contract for dispatching structured dossiers into Monday.com Work OS."""
    board_id: int = Field(..., description="Target Monday board identifier")
    group_id: str = Field(..., min_length=1, description="Target board group identifier")
    item_name: str = Field(..., min_length=1, description="Item display title")
    column_values: dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary mapping Monday column IDs to JSON-compatible values"
    )


class BatchExportStatus(BaseModel):
    """Telemetry report recording batch processing throughput and success rate."""
    total_processed: int = Field(default=0, ge=0, description="Total records in batch")
    exported_count: int = Field(default=0, ge=0, description="Successfully exported records")
    failed_count: int = Field(default=0, ge=0, description="Failed records")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC batch completion timestamp"
    )

    @property
    def success_rate(self) -> float:
        if self.total_processed == 0:
            return 100.0
        return round((self.exported_count / self.total_processed) * 100, 2)
