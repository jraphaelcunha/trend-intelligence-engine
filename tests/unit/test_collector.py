"""
Unit tests for YouTube video collection and filtering logic in src/collector.py.
"""

from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from src.collector import run_collection, save_to_database, search_youtube_videos


@pytest.fixture
def sample_collector_config():
    return {
        "theme": {"name": "World Cup 2026"},
        "search": {
            "date_start": "2026-01-01",
            "max_videos_per_subtopic": 10,
            "order_by": "viewCount",
            "regions": [
                {"label": "Brasil", "code": "BR", "language": "pt"}
            ],
            "min_views": 1000,
            "min_engagement_ratio": 0.01,
            "advanced_metrics": {
                "enabled": True,
                "recent_video_days": 7,
                "recent_min_views": 500,
                "min_views_per_day": 50,
                "recent_min_views_per_day": 50,
            },
        },
        "subtopics": [
            {
                "id": "tatica",
                "name": "Tática de Jogos",
                "keywords": ["tática copa 2026"],
            }
        ],
    }


def test_search_youtube_videos_missing_client(monkeypatch, sample_collector_config):
    """Verify ValueError is raised if YouTube API client is not initialized."""
    monkeypatch.setattr("src.collector.youtube", None)
    with pytest.raises(ValueError, match="YOUTUBE_API_KEY não configurada"):
        search_youtube_videos("copa 2026", "tatica", sample_collector_config)


def test_search_youtube_videos_empty_results(monkeypatch, sample_collector_config):
    """Verify empty list is returned when YouTube search returns no videos."""
    mock_youtube = MagicMock()
    mock_search = MagicMock()
    mock_search.execute.return_value = {"items": []}
    mock_youtube.search.return_value.list.return_value = mock_search
    monkeypatch.setattr("src.collector.youtube", mock_youtube)

    results = search_youtube_videos("copa 2026", "tatica", sample_collector_config)
    assert results == []


def test_search_youtube_videos_batch_statistics_and_filtering(monkeypatch, sample_collector_config):
    """Verify batch stats retrieval (1 API call) and metric filtering."""
    mock_youtube = MagicMock()
    
    # 1. Search response with 2 items
    mock_search = MagicMock()
    mock_search.execute.return_value = {
        "items": [
            {
                "id": {"videoId": "vid_high_eng"},
                "snippet": {
                    "title": "High Engagement Video",
                    "description": "Tactical breakdown",
                    "channelTitle": "TacticsHub",
                    "channelId": "UC_tactics_123",
                    "publishedAt": "2026-06-01T12:00:00Z",
                },
            },
            {
                "id": {"videoId": "vid_low_eng"},
                "snippet": {
                    "title": "Low Engagement Video",
                    "description": "Boring video",
                    "channelTitle": "SpamChannel",
                    "channelId": "UC_spam_456",
                    "publishedAt": "2026-06-01T12:00:00Z",
                },
            },
        ]
    }
    mock_youtube.search.return_value.list.return_value = mock_search

    # 2. Batch statistics response
    mock_stats = MagicMock()
    mock_stats.execute.return_value = {
        "items": [
            {
                "id": "vid_high_eng",
                "statistics": {
                    "viewCount": "10000",
                    "likeCount": "500",
                    "commentCount": "200",  # ratio: 200/10000 = 0.02 >= 0.01
                },
            },
            {
                "id": "vid_low_eng",
                "statistics": {
                    "viewCount": "20000",
                    "likeCount": "50",
                    "commentCount": "10",  # ratio: 10/20000 = 0.0005 < 0.01 -> filtered out
                },
            },
        ]
    }
    mock_youtube.videos.return_value.list.return_value = mock_stats
    monkeypatch.setattr("src.collector.youtube", mock_youtube)

    results = search_youtube_videos(
        query="tática copa 2026",
        subtopic_id="tatica",
        config=sample_collector_config,
        published_after="2026-01-01",
    )

    # Should retain vid_high_eng and filter out vid_low_eng
    assert len(results) == 1
    assert results[0]["post_url"] == "https://www.youtube.com/watch?v=vid_high_eng"
    assert results[0]["views_count"] == 10000
    assert results[0]["comments_count"] == 200
    assert results[0]["subtopic"] == "tatica"

    # Verify batch statistics call passed comma-separated IDs
    mock_youtube.videos.return_value.list.assert_called_once_with(
        id="vid_high_eng,vid_low_eng",
        part="statistics",
    )


def test_save_to_database_empty():
    """Verify save_to_database returns 0 immediately when input list is empty."""
    assert save_to_database([]) == 0


def test_save_to_database_success():
    """Verify execute_values is called and connection is closed on success."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    videos = [
        {
            "platform": "youtube",
            "post_url": "https://www.youtube.com/watch?v=123",
            "author_name": "Channel",
            "author_handle": "Channel",
            "content_title": "Video Title",
            "content_description": "Desc",
            "published_at": "2026-06-01T12:00:00Z",
            "views_count": 5000,
            "likes_count": 250,
            "comments_count": 50,
            "subtopic": "tatica",
            "scraped_at": "2026-06-02T12:00:00Z",
        }
    ]

    with patch("src.collector.get_connection", return_value=mock_conn):
        with patch("src.collector.execute_values") as mock_exec_values:
            saved = save_to_database(videos)
            assert saved == 1
            mock_exec_values.assert_called_once()
            assert mock_conn.autocommit is True
            mock_conn.close.assert_called_once()


def test_save_to_database_error():
    """Verify save_to_database catches psycopg2.Error and returns 0."""
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = psycopg2.DatabaseError("DB write failure")

    videos = [{"platform": "youtube", "post_url": "url", "author_name": "A", "author_handle": "A",
              "content_title": "T", "content_description": "D", "published_at": "now",
              "views_count": 1, "likes_count": 1, "comments_count": 1, "subtopic": "s", "scraped_at": "now"}]

    with patch("src.collector.get_connection", return_value=mock_conn):
        saved = save_to_database(videos)
        assert saved == 0
        mock_conn.close.assert_called_once()


def test_run_collection_flow(sample_collector_config):
    """Verify run_collection parses config, calls search and save."""
    with patch("src.collector.load_config", return_value=sample_collector_config):
        with patch("src.collector.search_youtube_videos", return_value=[{"post_url": "url1"}]):
            with patch("src.collector.save_to_database", return_value=1) as mock_save:
                run_collection("dummy_path.yaml")
                mock_save.assert_called_once()
