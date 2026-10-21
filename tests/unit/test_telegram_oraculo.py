"""
Unit tests for Telegram RAG Oráculo service in src/telegram_oraculo.py.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg2

from src.telegram_oraculo import (
    generate_rag_answer,
    get_query_embedding,
    handle_message,
    search_supabase_fallback,
    search_supabase_vector,
    start,
)


def test_get_query_embedding():
    """Verify embedding conversion via genai.embed_content."""
    mock_embed_res = {"embedding": [0.1, 0.2, 0.3, 0.4]}
    with patch("src.telegram_oraculo.genai.embed_content", return_value=mock_embed_res):
        emb = get_query_embedding("Qual a melhor tática?")
        assert emb == [0.1, 0.2, 0.3, 0.4]


def test_search_supabase_vector_success():
    """Verify vector search executes match_post_analysis and returns dict records."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.description = [("id",), ("content_title",), ("similarity",)]
    mock_cur.fetchall.return_value = [(101, "Vídeo Copa 2026", 0.88)]
    mock_conn.cursor.return_value = mock_cur

    with patch("psycopg2.connect", return_value=mock_conn):
        results = search_supabase_vector([0.1, 0.2], match_threshold=0.3, match_count=5)
        assert len(results) == 1
        assert results[0]["id"] == 101
        assert results[0]["content_title"] == "Vídeo Copa 2026"
        assert results[0]["similarity"] == 0.88
        mock_conn.close.assert_called_once()


def test_search_supabase_vector_db_error():
    """Verify vector search returns empty list on DB error."""
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = psycopg2.DatabaseError("PG connection dropped")

    with patch("psycopg2.connect", return_value=mock_conn):
        results = search_supabase_vector([0.1, 0.2])
        assert results == []
        mock_conn.close.assert_called_once()


def test_search_supabase_fallback_success():
    """Verify relational fallback query returns latest dossiers."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.description = [
        ("id",), ("post_id",), ("content_title",), ("video_tone",),
        ("editing_style",), ("content_summary",), ("audience_pain_points",), ("strategic_insights",)
    ]
    mock_cur.fetchall.return_value = [
        (1, 10, "Título Fallback", "Crítico", "Cortes", "Resumo", "Dor", "Insights")
    ]
    mock_conn.cursor.return_value = mock_cur

    with patch("psycopg2.connect", return_value=mock_conn):
        results = search_supabase_fallback()
        assert len(results) == 1
        assert results[0]["content_title"] == "Título Fallback"
        mock_conn.close.assert_called_once()


def test_search_supabase_fallback_db_error():
    """Verify relational fallback returns empty list on error."""
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = psycopg2.DatabaseError("Table missing")

    with patch("psycopg2.connect", return_value=mock_conn):
        results = search_supabase_fallback()
        assert results == []
        mock_conn.close.assert_called_once()


def test_generate_rag_answer_empty_records():
    """Verify graceful response when no contextual records are found."""
    ans = generate_rag_answer("Pergunta qualquer", [])
    assert "Ainda não encontrei informações suficientes" in ans


def test_generate_rag_answer_with_records():
    """Verify prompt formatting and LLM response generation."""
    records = [
        {
            "content_title": "Análise da Copa",
            "video_tone": "Otimista",
            "editing_style": "Dinâmico",
            "content_summary": "Previsão de convocação",
            "audience_pain_points": "Preço alto dos ingressos",
            "strategic_insights": "Foco em torcida jovem",
        }
    ]

    mock_resp = MagicMock()
    mock_resp.text = "Resposta do estrategista: A torcida está animada mas preocupada com custos."

    with patch("src.telegram_oraculo.CHAT_MODEL.generate_content", return_value=mock_resp) as mock_gen:
        ans = generate_rag_answer("O que acham dos preços?", records)
        assert ans == "Resposta do estrategista: A torcida está animada mas preocupada com custos."
        prompt_sent = mock_gen.call_args[0][0]
        assert "Análise da Copa" in prompt_sent
        assert "Preço alto dos ingressos" in prompt_sent


def test_telegram_start_command():
    """Verify /start command sends welcome message."""
    mock_update = MagicMock()
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    asyncio.run(start(mock_update, mock_context))
    mock_update.message.reply_text.assert_awaited_once()
    assert "Oráculo do Trend Intelligence Engine" in mock_update.message.reply_text.call_args[0][0]


def test_telegram_handle_message_with_fallback():
    """Verify handle_message triggers relational fallback when vector search returns 0 results."""
    mock_update = MagicMock()
    mock_update.message.text = "Quais as principais polêmicas?"
    mock_thinking = MagicMock()
    mock_thinking.edit_text = AsyncMock()
    mock_update.message.reply_text = AsyncMock(return_value=mock_thinking)
    mock_context = MagicMock()

    fallback_records = [{"content_title": "Fallback Post", "strategic_insights": "Insight"}]

    with patch("src.telegram_oraculo.get_query_embedding", return_value=[0.1, 0.2]):
        with patch("src.telegram_oraculo.search_supabase_vector", return_value=[]):
            with patch("src.telegram_oraculo.search_supabase_fallback", return_value=fallback_records) as mock_fallback:
                with patch("src.telegram_oraculo.generate_rag_answer", return_value="Resposta gerada") as mock_rag:
                    asyncio.run(handle_message(mock_update, mock_context))
                    mock_fallback.assert_called_once()
                    mock_rag.assert_called_once_with("Quais as principais polêmicas?", fallback_records)
                    mock_thinking.edit_text.assert_awaited_once_with("Resposta gerada")
