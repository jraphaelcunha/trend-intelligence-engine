"""
Unit tests for database connection resilience, retries, and query execution.
"""

from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from src.utils.db import execute_query, get_connection


def test_get_connection_missing_url(monkeypatch):
    """Verify ValueError is raised if DATABASE_URL is not set."""
    monkeypatch.setattr("src.utils.db.DATABASE_URL", None)
    with pytest.raises(ValueError, match="DATABASE_URL não está configurada"):
        get_connection()


def test_get_connection_success(monkeypatch):
    """Verify successful connection returns a psycopg2 connection object."""
    monkeypatch.setattr("src.utils.db.DATABASE_URL", "postgresql://test:test@localhost:5432/db")
    mock_conn = MagicMock()
    with patch("psycopg2.connect", return_value=mock_conn):
        conn = get_connection()
        assert conn == mock_conn


def test_get_connection_retry_and_eventual_success(monkeypatch):
    """Verify connection retries on OperationalError and succeeds if recovered."""
    monkeypatch.setattr("src.utils.db.DATABASE_URL", "postgresql://test:test@localhost:5432/db")
    mock_conn = MagicMock()
    with patch("psycopg2.connect", side_effect=[psycopg2.OperationalError("Temporary network glitch"), mock_conn]):
        with patch("time.sleep", return_value=None) as mock_sleep:
            conn = get_connection(retries=3, delay=1)
            assert conn == mock_conn
            assert mock_sleep.call_count == 1


def test_get_connection_max_retries_exceeded(monkeypatch):
    """Verify OperationalError is raised when all retries are exhausted."""
    monkeypatch.setattr("src.utils.db.DATABASE_URL", "postgresql://test:test@localhost:5432/db")
    with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("Persistent connection failure")):
        with patch("time.sleep", return_value=None):
            with pytest.raises(psycopg2.OperationalError):
                get_connection(retries=3, delay=1)


def test_execute_query_fetch(monkeypatch):
    """Verify execute_query executes and returns fetched rows when fetch=True."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = [("row1", 100), ("row2", 200)]
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    with patch("src.utils.db.get_connection", return_value=mock_conn):
        rows = execute_query("SELECT id, val FROM tbl WHERE id = %s", params=(1,), fetch=True)
        assert rows == [("row1", 100), ("row2", 200)]
        mock_cur.execute.assert_called_once_with("SELECT id, val FROM tbl WHERE id = %s", (1,))
        mock_conn.close.assert_called_once()


def test_execute_query_no_fetch(monkeypatch):
    """Verify execute_query executes without fetch and closes connection."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    with patch("src.utils.db.get_connection", return_value=mock_conn):
        res = execute_query("UPDATE tbl SET val = %s", params=(50,), fetch=False)
        assert res is None
        mock_cur.execute.assert_called_once_with("UPDATE tbl SET val = %s", (50,))
        mock_conn.close.assert_called_once()
