"""
Unit tests for n8n webhook exporter in src/n8n_exporter.py.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests

from src.n8n_exporter import N8N_HTTP_TIMEOUT, export_to_n8n


def test_export_to_n8n_missing_webhook_url(monkeypatch):
    """Verify early return when N8N_WEBHOOK_URL is not configured."""
    monkeypatch.setattr("src.n8n_exporter.N8N_WEBHOOK_URL", None)
    with patch("psycopg2.connect") as mock_conn:
        export_to_n8n()
        mock_conn.assert_not_called()


def test_export_to_n8n_no_pending_records(monkeypatch):
    """Verify clean exit when no records need export."""
    monkeypatch.setattr("src.n8n_exporter.N8N_WEBHOOK_URL", "https://n8n.example.com/webhook/test")
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cur

    with patch("psycopg2.connect", return_value=mock_conn):
        with patch("requests.post") as mock_http:
            export_to_n8n()
            mock_http.assert_not_called()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()


def test_export_to_n8n_success(monkeypatch):
    """Verify serializing records, POSTing to webhook, and marking records exported."""
    monkeypatch.setattr("src.n8n_exporter.N8N_WEBHOOK_URL", "https://n8n.example.com/webhook/test")
    mock_conn = MagicMock()
    mock_cur = MagicMock()

    records = [
        {
            "post_id": 1,
            "analysis_id": 10,
            "content_title": "Vídeo Copa",
            "post_url": "https://youtube.com/watch?v=xyz",
            "views_count": 1000,
            "likes_count": 100,
            "comments_count": 20,
            "subtopic": "tatica",
            "published_at": None,
            "video_tone": "Otimista",
            "editing_style": "Cortes",
            "content_summary": "Resumo",
            "audience_pain_points": ["Dor 1"],
            "public_sentiment": "Positivo",
            "algorithm_relevance_score": Decimal("8.5"),
        }
    ]

    mock_cur.fetchall.return_value = records
    mock_conn.cursor.return_value = mock_cur

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("psycopg2.connect", return_value=mock_conn):
        with patch("requests.post", return_value=mock_resp) as mock_http:
            with patch("time.sleep", return_value=None):
                export_to_n8n()
                mock_http.assert_called_once()
                # Verify decimal conversion in payload
                sent_json = mock_http.call_args[1]["json"]
                assert sent_json["algorithm_relevance_score"] == 8.5
                # Verify update query marking as exported
                mock_cur.execute.assert_called_with(
                    "UPDATE public.post_ai_analysis SET exported_to_zapier = TRUE WHERE id::text = ANY(%s)",
                    ([10],)
                )
                mock_conn.commit.assert_called_once()


def test_export_to_n8n_timeout(monkeypatch):
    """Verify that a timeout on n8n webhook skips exporting the record and prevents commit."""
    monkeypatch.setattr("src.n8n_exporter.N8N_WEBHOOK_URL", "https://n8n.example.com/webhook/test")
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    records = [
        {
            "post_id": 1,
            "analysis_id": 10,
            "content_title": "Vídeo n8n Timeout",
            "post_url": "https://youtube.com/watch?v=xyz",
            "views_count": 1000,
            "likes_count": 100,
            "comments_count": 20,
            "subtopic": "tatica",
            "published_at": None,
            "video_tone": "Otimista",
            "editing_style": "Cortes",
            "content_summary": "Resumo",
            "audience_pain_points": ["Dor 1"],
            "public_sentiment": "Positivo",
            "algorithm_relevance_score": Decimal("8.5"),
        }
    ]
    mock_cur.fetchall.return_value = records
    mock_conn.cursor.return_value = mock_cur

    with patch("psycopg2.connect", return_value=mock_conn):
        with patch("requests.post", side_effect=requests.exceptions.Timeout("n8n timeout")) as mock_http:
            with patch("time.sleep", return_value=None):
                export_to_n8n()
                mock_http.assert_called_once()
                assert mock_http.call_args[1].get("timeout") == N8N_HTTP_TIMEOUT
                mock_conn.commit.assert_not_called()

