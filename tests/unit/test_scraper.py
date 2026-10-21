"""
Unit tests for YouTube comment scraping and storage logic in src/scraper.py.
"""

from unittest.mock import MagicMock, patch

import psycopg2
from googleapiclient.errors import HttpError

from src.scraper import (
    extract_video_id,
    fetch_comments_via_api,
    get_videos_needing_comments,
    run_comment_scraper,
    save_comments_to_db,
)


def test_scraper_extract_video_id():
    """Verify regex/string splitting for standard and short YouTube URLs."""
    assert extract_video_id("https://www.youtube.com/watch?v=abcd1234efg") == "abcd1234efg"
    assert extract_video_id("https://youtu.be/shortId123?t=10") == "shortId123"
    assert extract_video_id("https://example.com/not-a-video") is None


def test_scraper_get_videos_needing_comments_success():
    """Verify retrieving pending videos from DB."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = [(1, "https://www.youtube.com/watch?v=vid1"), (2, "https://www.youtube.com/watch?v=vid2")]
    mock_conn.cursor.return_value = mock_cur

    with patch("src.scraper.get_connection", return_value=mock_conn):
        videos = get_videos_needing_comments()
        assert len(videos) == 2
        mock_cur.execute.assert_called_once()
        mock_conn.close.assert_called_once()


def test_scraper_get_videos_needing_comments_db_error():
    """Verify DB error returns empty list and closes connection."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute.side_effect = psycopg2.DatabaseError("Connection dropped")
    mock_conn.cursor.return_value = mock_cur

    with patch("src.scraper.get_connection", return_value=mock_conn):
        videos = get_videos_needing_comments()
        assert videos == []
        mock_conn.close.assert_called_once()


def test_scraper_fetch_comments_via_api_success(monkeypatch):
    """Verify parsing topLevelComment from YouTube commentThreads API response."""
    mock_youtube = MagicMock()
    mock_threads = MagicMock()
    mock_threads.execute.return_value = {
        "items": [
            {
                "snippet": {
                    "topLevelComment": {
                        "snippet": {
                            "authorDisplayName": "Torcedor1",
                            "textDisplay": "Excelente análise tática!",
                            "likeCount": 150,
                            "publishedAt": "2026-06-01T15:00:00Z",
                        }
                    }
                }
            }
        ]
    }
    mock_youtube.commentThreads.return_value.list.return_value = mock_threads
    monkeypatch.setattr("src.scraper.youtube", mock_youtube)

    comments = fetch_comments_via_api("test_vid_id", max_results=10)
    assert len(comments) == 1
    assert comments[0]["author_name"] == "Torcedor1"
    assert comments[0]["comment_text"] == "Excelente análise tática!"
    assert comments[0]["likes_count"] == 150


def test_scraper_fetch_comments_via_api_disabled(monkeypatch):
    """Verify graceful handling when comments are disabled on the video."""
    mock_youtube = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 403
    mock_error = HttpError(resp=mock_resp, content=b'{"error": {"errors": [{"reason": "commentsDisabled"}]}}')
    mock_youtube.commentThreads.return_value.list.return_value.execute.side_effect = mock_error
    monkeypatch.setattr("src.scraper.youtube", mock_youtube)

    comments = fetch_comments_via_api("disabled_comments_vid")
    assert comments == []


def test_scraper_save_comments_to_db_empty():
    """Verify early return when comments list is empty."""
    with patch("src.scraper.get_connection") as mock_conn:
        save_comments_to_db(1, [])
        mock_conn.assert_not_called()


def test_scraper_save_comments_to_db_success():
    """Verify DELETE + execute_values pattern for idempotency."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    comments = [
        {
            "author_name": "UserA",
            "comment_text": "Nice video",
            "likes_count": 10,
            "published_at": "2026-06-01T12:00:00Z",
        }
    ]

    with patch("src.scraper.get_connection", return_value=mock_conn):
        with patch("src.scraper.execute_values") as mock_exec_values:
            save_comments_to_db(10, comments)
            mock_cur.execute.assert_called_once_with(
                "DELETE FROM public.post_comments WHERE post_id = %s", (10,)
            )
            mock_exec_values.assert_called_once()
            mock_conn.close.assert_called_once()


def test_scraper_save_comments_to_db_error():
    """Verify DB error during save is handled and connection is closed."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute.side_effect = psycopg2.DatabaseError("Insert failed")
    mock_conn.cursor.return_value = mock_cur

    comments = [{"author_name": "User", "comment_text": "Text", "likes_count": 0, "published_at": "now"}]

    with patch("src.scraper.get_connection", return_value=mock_conn):
        save_comments_to_db(10, comments)
        mock_conn.close.assert_called_once()


def test_run_comment_scraper_no_videos():
    """Verify run_comment_scraper returns early when no videos need comments."""
    with patch("src.scraper.get_videos_needing_comments", return_value=[]):
        with patch("src.scraper.fetch_comments_via_api") as mock_fetch:
            run_comment_scraper()
            mock_fetch.assert_not_called()


def test_run_comment_scraper_flow(monkeypatch):
    """Verify run_comment_scraper iterates videos, fetches and saves comments."""
    monkeypatch.setattr("src.scraper.YOUTUBE_API_KEY", "dummy_key")
    monkeypatch.setattr("src.scraper.youtube", MagicMock())

    videos = [(101, "https://www.youtube.com/watch?v=vid101")]
    comments = [{"author_name": "A", "comment_text": "C", "likes_count": 5, "published_at": "now"}]

    with patch("src.scraper.get_videos_needing_comments", return_value=videos):
        with patch("src.scraper.fetch_comments_via_api", return_value=comments) as mock_fetch:
            with patch("src.scraper.save_comments_to_db") as mock_save:
                with patch("time.sleep", return_value=None):
                    run_comment_scraper()
                    mock_fetch.assert_called_once_with("vid101", max_results=100)
                    mock_save.assert_called_once_with(101, comments)
