"""
Unit tests for fetcher and Monday.com transformation helpers.
"""

from unittest.mock import MagicMock, patch

from src.fetcher import (
    clean_string,
    extract_section,
    format_pain_points_and_sentiment,
    get_existing_monday_groups,
    map_sentiment,
)


def test_map_sentiment_positive():
    assert map_sentiment("Muito positivo e elogiou o produto") == "Positivo"
    assert map_sentiment("Bom desempenho e otimo resultado") == "Positivo"


def test_map_sentiment_negative():
    assert map_sentiment("Crítica severa com pessimo atendimento") == "Negativo"
    assert map_sentiment("Reclamou muito da instabilidade") == "Negativo"


def test_map_sentiment_neutral():
    assert map_sentiment("Comentário neutro e apenas informativo") == "Neutro"


def test_map_sentiment_inconclusive_fallback():
    assert map_sentiment(None) == "Inconclusivo"
    assert map_sentiment("") == "Inconclusivo"
    assert map_sentiment("xyz123") == "Inconclusivo"


def test_format_pain_points_and_sentiment_with_list():
    pain_points = ["Lentidão no carregamento", "Falta de suporte"]
    result = format_pain_points_and_sentiment(pain_points, "Predominantemente Negativo")
    assert "Lentidão no carregamento" in result
    assert "Falta de suporte" in result
    assert "Predominantemente Negativo" in result


def test_format_pain_points_empty():
    result = format_pain_points_and_sentiment([], None)
    assert result == "Nenhuma dor detectada"


def test_extract_section():
    full_text = "INTRO: Starting now. TOPICS: Topic A, Topic B. CONCLUSION: All done."
    extracted = extract_section(full_text, "TOPICS:", "CONCLUSION:")
    assert extracted == "Topic A, Topic B."


def test_clean_string_truncation():
    long_string = "a" * 300
    cleaned = clean_string(long_string, max_len=255)
    assert len(cleaned) == 255


@patch("src.fetcher.requests.post")
def test_get_existing_monday_groups(mock_post, mock_monday_groups_payload, monkeypatch):
    monkeypatch.setattr("src.fetcher.MONDAY_API_TOKEN", "mock_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_monday_groups_payload
    mock_post.return_value = mock_resp

    groups = get_existing_monday_groups()
    assert "tática e react de jogos" in groups
    assert groups["tática e react de jogos"] == "topics_tatica"
