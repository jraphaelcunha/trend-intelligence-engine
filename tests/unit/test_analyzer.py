"""
Unit tests for analyzer module and video extraction logic.
"""

from src.analyzer import extract_video_id, get_subtopic_context


def test_extract_video_id_standard_url():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_with_query_params():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=share&t=10s"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_shortened_url():
    url = "https://youtu.be/dQw4w9WgXcQ?si=abcdef123456"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_invalid_url():
    url = "https://example.com/video/12345"
    assert extract_video_id(url) is None


def test_get_subtopic_context():
    mock_config = {
        "subtopics": [
            {"id": "tatica", "name": "Tática", "analysis_angle": "Foco em formações"},
            {"id": "figurinhas", "name": "Figurinhas", "analysis_angle": "Preço de pacotes"}
        ]
    }
    name, angle = get_subtopic_context("tatica", mock_config)
    assert name == "Tática"
    assert angle == "Foco em formações"

    name_unknown, angle_unknown = get_subtopic_context("nao_existe", mock_config)
    assert name_unknown == ""
    assert angle_unknown == ""
