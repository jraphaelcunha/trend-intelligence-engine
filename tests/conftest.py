"""
Pytest fixtures and deterministic test configurations for Trend Intelligence Engine.
"""


import pytest
from src.models.schemas import CommentPayload, SentimentAnalysisResult, VideoMetadata


@pytest.fixture
def sample_video_metadata():
    """Valid VideoMetadata instance for testing."""
    return VideoMetadata(
        video_id="dQw4w9WgXcQ",
        title="World Cup 2026 Opening Match Preview & Tactics",
        channel_title="Tactical Football Analytics",
        view_count=154200,
        like_count=9800,
        comment_count=1240,
        subtopic_id="tatica",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )


@pytest.fixture
def sample_comment_payload():
    """Valid CommentPayload instance for batch sentiment testing."""
    return CommentPayload(
        comment_id="UgxK99_Abc123xyz",
        video_id="dQw4w9WgXcQ",
        author="FutFan2026",
        text="A escalação no meio de campo foi arriscada demais, faltou marcação na transição defensiva!",
        like_count=45
    )


@pytest.fixture
def sample_sentiment_result():
    """Structured SentimentAnalysisResult model fixture."""
    return SentimentAnalysisResult(
        sentiment="Negativo",
        summary="A maioria dos torcedores criticou a falta de marcação e lentidão na recomposição tática.",
        pain_points=[
            "Transição defensiva desorganizada",
            "Falta de cobertura dos laterais"
        ],
        key_takeaways=[
            "Torcida exige volante de marcação titular",
            "Crítica unânime à lentidão do primeiro tempo"
        ],
        confidence_score=0.92
    )


@pytest.fixture
def mock_monday_groups_payload():
    """GraphQL response mock for Monday board groups."""
    return {
        "data": {
            "boards": [
                {
                    "groups": [
                        {"id": "topics_tatica", "title": "Tática e React de Jogos"},
                        {"id": "topics_figurinhas", "title": "Figurinhas da Copa 2026"},
                        {"id": "topics_geral", "title": "Geral e Outros Temas"}
                    ]
                }
            ]
        }
    }
