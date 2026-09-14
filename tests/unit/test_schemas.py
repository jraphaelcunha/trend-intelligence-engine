"""
Unit tests for Pydantic v2 data contracts and models.
"""

import pytest
from pydantic import ValidationError
from src.models.schemas import (
    VideoMetadata,
    CommentPayload,
    SentimentAnalysisResult,
    MondayItemPayload,
    BatchExportStatus
)


def test_video_metadata_valid(sample_video_metadata):
    """Verify proper initialization and field retention for VideoMetadata."""
    assert sample_video_metadata.video_id == "dQw4w9WgXcQ"
    assert sample_video_metadata.view_count == 154200
    assert sample_video_metadata.subtopic_id == "tatica"


def test_video_metadata_invalid_url():
    """Verify validation error when video_url does not start with http/https."""
    with pytest.raises(ValidationError):
        VideoMetadata(
            video_id="test_id",
            title="Invalid URL Video",
            video_url="ftp://invalid.url"
        )


def test_comment_payload_defaults():
    """Verify default values in CommentPayload."""
    comment = CommentPayload(
        comment_id="c_001",
        video_id="v_001",
        text="Great tactical overview!"
    )
    assert comment.author == "Anonymous"
    assert comment.like_count == 0


def test_sentiment_analysis_result_validation(sample_sentiment_result):
    """Verify sentiment categorization and bounds."""
    assert sample_sentiment_result.sentiment == "Negativo"
    assert len(sample_sentiment_result.pain_points) == 2
    assert 0.0 <= sample_sentiment_result.confidence_score <= 1.0


def test_sentiment_invalid_sentiment_literal():
    """Verify that invalid sentiment literals raise validation error."""
    with pytest.raises(ValidationError):
        SentimentAnalysisResult(
            sentiment="ExtremamenteFeliz",  # Not in Literal
            summary="Invalid sentiment test"
        )


def test_batch_export_status_success_rate():
    """Verify success rate computation in BatchExportStatus."""
    status = BatchExportStatus(
        total_processed=100,
        exported_count=95,
        failed_count=5
    )
    assert status.success_rate == 95.0

    empty_status = BatchExportStatus()
    assert empty_status.success_rate == 100.0
