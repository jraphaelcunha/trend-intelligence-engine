"""
Unit tests for Monday.com export service in src/export_to_monday.py.
"""

from unittest.mock import MagicMock, patch

import requests

from src.export_to_monday import MONDAY_HTTP_TIMEOUT, get_monday_headers, run_export


def test_get_monday_headers(monkeypatch):
    """Verify authorization and content-type headers for Monday.com API."""
    monkeypatch.setattr("src.export_to_monday.MONDAY_API_TOKEN", "mock_monday_token_xyz")
    headers = get_monday_headers()
    assert headers["Authorization"] == "mock_monday_token_xyz"
    assert headers["Content-Type"] == "application/json"


def test_run_export_no_api_token(monkeypatch):
    """Verify early exit when MONDAY_API_TOKEN is not configured."""
    monkeypatch.setattr("src.export_to_monday.MONDAY_API_TOKEN", None)
    with patch("psycopg2.connect") as mock_conn:
        run_export()
        mock_conn.assert_not_called()


def test_run_export_no_pending_records(monkeypatch):
    """Verify clean exit when no records need export."""
    monkeypatch.setattr("src.export_to_monday.MONDAY_API_TOKEN", "valid_token")
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cur

    with patch("src.export_to_monday.get_existing_monday_groups", return_value={"geral": "grp_1"}):
        with patch("psycopg2.connect", return_value=mock_conn):
            with patch("requests.post") as mock_http:
                run_export()
                mock_http.assert_not_called()
                mock_cur.close.assert_called_once()
                mock_conn.close.assert_called_once()


def test_run_export_successful_item_and_update_creation(monkeypatch):
    """Verify item creation, rich-text update, and Supabase status marking."""
    monkeypatch.setattr("src.export_to_monday.MONDAY_API_TOKEN", "valid_token")
    mock_conn = MagicMock()
    mock_cur = MagicMock()

    pending_records = [
        {
            "post_id": 101,
            "analysis_id": 501,
            "subtopic": "tatica",
            "content_title": "Análise Estratégica",
            "post_url": "https://youtube.com/watch?v=abc",
            "views_count": 25000,
            "likes_count": 1200,
            "comments_count": 150,
            "published_at": "2026-06-01T12:00:00Z",
            "video_tone": "Técnico",
            "editing_style": "Cortes Rápidos",
            "content_summary": "--- NARRATIVA DO VÍDEO ---\nTese do criador\n--- REAÇÃO DO PÚBLICO ---\nPúblico aprova",
            "audience_pain_points": ["Falta criatividade"],
            "public_sentiment": "Positivo",
            "algorithm_relevance_score": 8.9,
            "strategic_insights": "--- ANÁLISE COMPARATIVA ---\nAlinhado\n--- INSIGHTS ESTRATÉGICOS ---\nApostar no tema",
        }
    ]

    top_comments = [
        {"author_name": "Fan1", "comment_text": "Grande vídeo!", "likes_count": 80}
    ]

    # First fetchall returns pending records, second returns top comments
    mock_cur.fetchall.side_effect = [pending_records, top_comments]
    mock_conn.cursor.return_value = mock_cur

    # Mock responses for Monday API calls: 1) create_item, 2) create_update
    resp_create_item = MagicMock()
    resp_create_item.status_code = 200
    resp_create_item.json.return_value = {"data": {"create_item": {"id": "monday_item_999"}}}

    resp_create_update = MagicMock()
    resp_create_update.status_code = 200
    resp_create_update.json.return_value = {"data": {"create_update": {"id": "monday_update_888"}}}

    with patch("src.export_to_monday.get_existing_monday_groups", return_value={"tática e react de jogos": "grp_tatica"}):
        with patch("psycopg2.connect", return_value=mock_conn):
            with patch("requests.post", side_effect=[resp_create_item, resp_create_update]) as mock_http:
                run_export()

                # Verify Monday item creation call
                assert mock_http.call_count == 2
                create_item_call = mock_http.call_args_list[0]
                assert "create_item" in create_item_call[1]["json"]["query"]
                assert create_item_call[1]["json"]["variables"]["groupId"] == "grp_tatica"

                # Verify Monday update call
                create_update_call = mock_http.call_args_list[1]
                assert "create_update" in create_update_call[1]["json"]["query"]
                assert create_update_call[1]["json"]["variables"]["itemId"] == "monday_item_999"

                # Verify Supabase update call
                mock_cur.execute.assert_any_call(
                    "UPDATE public.post_ai_analysis SET exported_to_zapier = TRUE WHERE id = %s",
                    (501,)
                )
                mock_conn.commit.assert_called_once()


def test_run_export_dynamic_group_creation(monkeypatch):
    """Verify group is created dynamically when not found in existing groups."""
    monkeypatch.setattr("src.export_to_monday.MONDAY_API_TOKEN", "valid_token")
    mock_conn = MagicMock()
    mock_cur = MagicMock()

    pending_records = [
        {
            "post_id": 102,
            "analysis_id": 502,
            "subtopic": "tatica",
            "content_title": "Vídeo Novo",
            "post_url": "https://youtube.com/watch?v=def",
            "views_count": 1000,
            "likes_count": 50,
            "comments_count": 10,
            "published_at": "2026-06-01T12:00:00Z",
            "video_tone": "Neutro",
            "editing_style": "Padrão",
            "content_summary": "",
            "audience_pain_points": [],
            "public_sentiment": "Neutro",
            "algorithm_relevance_score": 5.0,
            "strategic_insights": "",
        }
    ]

    mock_cur.fetchall.side_effect = [pending_records, []]
    mock_conn.cursor.return_value = mock_cur

    resp_item = MagicMock()
    resp_item.status_code = 200
    resp_item.json.return_value = {"data": {"create_item": {"id": "item_123"}}}

    resp_update = MagicMock()
    resp_update.status_code = 200
    resp_update.json.return_value = {"data": {"create_update": {"id": "up_123"}}}

    with patch("src.export_to_monday.get_existing_monday_groups", return_value={}):
        with patch("src.export_to_monday.create_monday_group", return_value="new_dynamic_group_id") as mock_create_grp:
            with patch("psycopg2.connect", return_value=mock_conn):
                with patch("requests.post", side_effect=[resp_item, resp_update]) as mock_http:
                    run_export()
                    mock_create_grp.assert_called_once_with("Tática e React de Jogos")
                    create_item_call = mock_http.call_args_list[0]
                    assert create_item_call[1]["json"]["variables"]["groupId"] == "new_dynamic_group_id"


def test_run_export_create_item_timeout(monkeypatch):
    """Verify that a timeout during item creation skips the record without updating Supabase."""
    monkeypatch.setattr("src.export_to_monday.MONDAY_API_TOKEN", "valid_token")
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    pending_records = [
        {
            "post_id": 101,
            "analysis_id": 501,
            "subtopic": "tatica",
            "content_title": "Vídeo Timeout",
            "post_url": "https://youtube.com/watch?v=timeout",
            "views_count": 1000,
            "likes_count": 10,
            "comments_count": 5,
            "published_at": None,
            "video_tone": "Neutro",
            "editing_style": "Cortes",
            "content_summary": "",
            "audience_pain_points": [],
            "public_sentiment": "Neutro",
            "algorithm_relevance_score": 5.0,
            "strategic_insights": "",
        }
    ]
    mock_cur.fetchall.side_effect = [pending_records, []]
    mock_conn.cursor.return_value = mock_cur

    with patch("src.export_to_monday.get_existing_monday_groups", return_value={"tática e react de jogos": "grp_tatica"}):
        with patch("psycopg2.connect", return_value=mock_conn):
            with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out")) as mock_http:
                run_export()
                mock_http.assert_called_once()
                assert mock_http.call_args[1].get("timeout") == MONDAY_HTTP_TIMEOUT
                # Confirm Supabase update was never executed
                for call in mock_cur.execute.call_args_list:
                    assert "UPDATE public.post_ai_analysis SET exported_to_zapier = TRUE" not in call[0][0]
                mock_conn.commit.assert_not_called()


def test_run_export_update_timeout_does_not_crash(monkeypatch):
    """Verify that update post timeout is handled gracefully after item creation succeeds."""
    monkeypatch.setattr("src.export_to_monday.MONDAY_API_TOKEN", "valid_token")
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    pending_records = [
        {
            "post_id": 101,
            "analysis_id": 501,
            "subtopic": "tatica",
            "content_title": "Vídeo Update Timeout",
            "post_url": "https://youtube.com/watch?v=timeout",
            "views_count": 1000,
            "likes_count": 10,
            "comments_count": 5,
            "published_at": None,
            "video_tone": "Neutro",
            "editing_style": "Cortes",
            "content_summary": "",
            "audience_pain_points": [],
            "public_sentiment": "Neutro",
            "algorithm_relevance_score": 5.0,
            "strategic_insights": "",
        }
    ]
    mock_cur.fetchall.side_effect = [pending_records, []]
    mock_conn.cursor.return_value = mock_cur

    resp_item = MagicMock()
    resp_item.status_code = 200
    resp_item.json.return_value = {"data": {"create_item": {"id": "monday_item_777"}}}

    with patch("src.export_to_monday.get_existing_monday_groups", return_value={"tática e react de jogos": "grp_tatica"}):
        with patch("psycopg2.connect", return_value=mock_conn):
            with patch("requests.post", side_effect=[resp_item, requests.exceptions.Timeout("Update timeout")]) as mock_http:
                run_export()
                assert mock_http.call_count == 2
                assert mock_http.call_args_list[0][1].get("timeout") == MONDAY_HTTP_TIMEOUT
                assert mock_http.call_args_list[1][1].get("timeout") == MONDAY_HTTP_TIMEOUT

