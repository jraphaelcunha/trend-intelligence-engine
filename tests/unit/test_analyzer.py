"""
Unit tests for analyzer module, prompt construction, dual-sampling, and database persistence.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg2

from src.analyzer import (
    analyze_post,
    extract_video_id,
    get_pending_posts,
    get_subtopic_context,
    get_transcript,
    run_analysis,
    save_analysis,
)


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
            {"id": "figurinhas", "name": "Figurinhas", "analysis_angle": "Preço de pacotes"},
        ]
    }
    name, angle = get_subtopic_context("tatica", mock_config)
    assert name == "Tática"
    assert angle == "Foco em formações"

    name_unknown, angle_unknown = get_subtopic_context("nao_existe", mock_config)
    assert name_unknown == ""
    assert angle_unknown == ""


def test_get_transcript_success():
    """Verify transcript segments are concatenated into a single string."""
    mock_segments = [
        SimpleNamespace(text="Olá a todos,"),
        SimpleNamespace(text="hoje falaremos sobre a Copa 2026."),
    ]
    with patch("src.analyzer.YouTubeTranscriptApi.fetch", return_value=mock_segments):
        transcript = get_transcript("test_vid_id")
        assert transcript == "Olá a todos, hoje falaremos sobre a Copa 2026."


def test_get_transcript_fallback_on_error():
    """Verify fallback message when transcript API raises an exception."""
    with patch("src.analyzer.YouTubeTranscriptApi.fetch", side_effect=Exception("Disabled")):
        transcript = get_transcript("disabled_vid")
        assert transcript == "Legenda indisponível."


def test_analyze_post_dual_sampling_over_100_comments():
    """Verify Dual-Sampling correctly slices top 10 and sample 100 comments."""
    post = {
        "id": 1,
        "url": "https://www.youtube.com/watch?v=vid123",
        "title": "Análise Tática do Brasil",
        "description": "Discussão tática profunda",
        "subtopic": "tatica",
    }
    # Create 120 comments
    comments = [{"author": f"User_{i}", "text": f"Comentário {i}", "likes": 120 - i} for i in range(120)]

    mock_config = {
        "subtopics": [{"id": "tatica", "name": "Tática", "analysis_angle": "Esquemas"}],
        "analysis": {"base_context": "Contexto Geral"},
    }

    mock_llm_response = {
        "video_tone": "Analítico",
        "editing_style": "Cortes rápidos",
        "content_summary": "Resumo do vídeo",
        "video_narrative": "Narrativa",
        "public_reaction": "Reação",
        "narrative_vs_reaction": "Comparação",
        "audience_pain_points": ["Escalação questionável"],
        "public_sentiment": "Positivo",
        "algorithm_relevance_score": 8.7,
        "strategic_insights": "Criar conteúdo sobre meio-campo",
    }

    mock_gen_result = MagicMock()
    mock_gen_result.text = f"```json\n{json.dumps(mock_llm_response)}\n```"

    with patch("src.analyzer.get_transcript", return_value="Transcrição simulada"):
        with patch("src.analyzer.model.generate_content", return_value=mock_gen_result) as mock_model:
            with patch("src.analyzer.save_analysis") as mock_save:
                success = analyze_post(post, comments, mock_config)
                assert success is True
                mock_save.assert_called_once()
                # Verify prompt received 10 top comments and 100 sample comments
                prompt_arg = mock_model.call_args[0][0]
                assert "AMOSTRA DOS 100 PRIMEIROS COMENTÁRIOS" in prompt_arg
                assert "PRINCIPAIS 10 COMENTÁRIOS MAIS CURTIDOS" in prompt_arg


def test_analyze_post_empty_comments():
    """Verify Dual-Sampling gracefully handles 0 comments."""
    post = {
        "id": 2,
        "url": "https://www.youtube.com/watch?v=vid_empty",
        "title": "Vídeo sem comentários",
        "description": "Desc",
        "subtopic": "tatica",
    }
    mock_config = {"subtopics": [], "analysis": {}}

    mock_llm_response = {
        "video_tone": "Informativo",
        "editing_style": "Padrão",
        "content_summary": "Resumo",
        "video_narrative": "Narrativa",
        "public_reaction": "Nenhuma reação",
        "narrative_vs_reaction": "Neutro",
        "audience_pain_points": [],
        "public_sentiment": "Neutro",
        "algorithm_relevance_score": 5.0,
        "strategic_insights": "Aguardar engajamento",
    }

    mock_gen_result = MagicMock()
    mock_gen_result.text = json.dumps(mock_llm_response)

    with patch("src.analyzer.get_transcript", return_value="Legenda indisponível."):
        with patch("src.analyzer.model.generate_content", return_value=mock_gen_result):
            with patch("src.analyzer.save_analysis") as mock_save:
                success = analyze_post(post, [], mock_config)
                assert success is True
                mock_save.assert_called_once()


def test_analyze_post_malformed_json_fallback():
    """Verify analyze_post returns False when LLM returns invalid JSON."""
    post = {"id": 3, "url": "https://www.youtube.com/watch?v=vid_err", "title": "T", "description": "D"}
    mock_config = {"subtopics": [], "analysis": {}}

    mock_gen_result = MagicMock()
    mock_gen_result.text = "This is not valid JSON content"

    with patch("src.analyzer.get_transcript", return_value=""):
        with patch("src.analyzer.model.generate_content", return_value=mock_gen_result):
            with patch("src.analyzer.save_analysis") as mock_save:
                success = analyze_post(post, [], mock_config)
                assert success is False
                mock_save.assert_not_called()


def test_analyze_post_sentiment_normalization():
    """Verify non-standard sentiment labels are coerced to 'Neutro'."""
    post = {"id": 4, "url": "https://www.youtube.com/watch?v=vid_sent", "title": "T", "description": "D"}
    mock_config = {"subtopics": [], "analysis": {}}

    mock_llm_response = {
        "video_tone": "Neutro",
        "editing_style": "Padrão",
        "content_summary": "Resumo",
        "video_narrative": "Narrativa",
        "public_reaction": "Reação",
        "narrative_vs_reaction": "Comparação",
        "audience_pain_points": [],
        "public_sentiment": "Misto/Inconclusivo",  # Invalid according to schema
        "algorithm_relevance_score": 6.0,
        "strategic_insights": "Insights",
    }

    mock_gen_result = MagicMock()
    mock_gen_result.text = json.dumps(mock_llm_response)

    with patch("src.analyzer.get_transcript", return_value=""):
        with patch("src.analyzer.model.generate_content", return_value=mock_gen_result):
            with patch("src.analyzer.save_analysis") as mock_save:
                success = analyze_post(post, [], mock_config)
                assert success is True
                # Saved analysis should have coerced sentiment to Neutro
                saved_result = mock_save.call_args[0][1]
                assert saved_result["public_sentiment"] == "Neutro"


def test_save_analysis_insert():
    """Verify database INSERT when existing_analysis_id is None."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    analysis_data = {
        "video_tone": "Crítico",
        "editing_style": "Vlog",
        "content_summary": "Resumo",
        "video_narrative": "Narrativa",
        "public_reaction": "Reação",
        "narrative_vs_reaction": "Comparação",
        "audience_pain_points": ["Preço"],
        "public_sentiment": "Negativo",
        "algorithm_relevance_score": 7.5,
        "strategic_insights": "Ajustar abordagem",
    }

    with patch("src.analyzer.genai.embed_content", return_value={"embedding": [0.1, 0.2, 0.3]}):
        with patch("src.analyzer.get_connection", return_value=mock_conn):
            save_analysis(post_id=42, analysis_json=analysis_data, existing_analysis_id=None)
            mock_cur.execute.assert_called_once()
            assert "INSERT INTO public.post_ai_analysis" in mock_cur.execute.call_args[0][0]
            mock_conn.close.assert_called_once()


def test_save_analysis_update():
    """Verify database UPDATE when existing_analysis_id is provided."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    analysis_data = {
        "video_tone": "Positivo",
        "editing_style": "Podcast",
        "content_summary": "Resumo",
        "video_narrative": "Narrativa",
        "public_reaction": "Reação",
        "narrative_vs_reaction": "Comparação",
        "audience_pain_points": [],
        "public_sentiment": "Positivo",
        "algorithm_relevance_score": 9.0,
        "strategic_insights": "Expandir cobertura",
    }

    with patch("src.analyzer.genai.embed_content", return_value={"embedding": [0.4, 0.5, 0.6]}):
        with patch("src.analyzer.get_connection", return_value=mock_conn):
            result = save_analysis(post_id=42, analysis_json=analysis_data, existing_analysis_id=999)
            assert result is True
            mock_cur.execute.assert_called_once()
            assert "UPDATE public.post_ai_analysis" in mock_cur.execute.call_args[0][0]
            mock_conn.close.assert_called_once()


def test_save_analysis_db_error_returns_false():
    """Verify save_analysis catches psycopg2.Error and returns False safely."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.execute.side_effect = psycopg2.DatabaseError("Connection lost")
    mock_conn.cursor.return_value = mock_cur

    analysis_data = {
        "video_tone": "Neutro",
        "editing_style": "Padrão",
        "content_summary": "Resumo",
        "video_narrative": "Narrativa",
        "public_reaction": "Reação",
        "narrative_vs_reaction": "Comparação",
        "audience_pain_points": [],
        "public_sentiment": "Neutro",
        "algorithm_relevance_score": 5.0,
        "strategic_insights": "Insights",
    }

    with patch("src.analyzer.genai.embed_content", return_value={"embedding": [0.1, 0.2]}):
        with patch("src.analyzer.get_connection", return_value=mock_conn):
            result = save_analysis(post_id=42, analysis_json=analysis_data)
            assert result is False
            mock_conn.close.assert_called_once()


def test_save_analysis_value_error_returns_false():
    """Verify save_analysis catches ValueError and returns False safely."""
    with patch("src.analyzer.genai.embed_content", side_effect=ValueError("Invalid embedding format")):
        result = save_analysis(post_id=42, analysis_json={})
        assert result is False


def test_analyze_post_db_failure_returns_false():
    """Verify analyze_post returns False when LLM succeeds but database persistence fails."""
    post = {"id": 10, "url": "https://www.youtube.com/watch?v=vid10", "title": "T", "description": "D"}
    mock_config = {"subtopics": [], "analysis": {}}

    mock_llm_response = {
        "video_tone": "Técnico",
        "editing_style": "Padrão",
        "content_summary": "Resumo",
        "video_narrative": "Narrativa",
        "public_reaction": "Reação",
        "narrative_vs_reaction": "Comparação",
        "audience_pain_points": [],
        "public_sentiment": "Positivo",
        "algorithm_relevance_score": 8.0,
        "strategic_insights": "Insights",
    }

    mock_gen_result = MagicMock()
    mock_gen_result.text = json.dumps(mock_llm_response)

    with patch("src.analyzer.get_transcript", return_value=""):
        with patch("src.analyzer.model.generate_content", return_value=mock_gen_result):
            with patch("src.analyzer.save_analysis", return_value=False) as mock_save:
                success = analyze_post(post, [], mock_config)
                assert success is False
                mock_save.assert_called_once()


def test_run_analysis_queue_exhaustion():
    """Verify run_analysis terminates immediately when get_pending_posts returns empty."""
    with patch("src.analyzer.load_config", return_value={"analysis": {}}):
        with patch("src.analyzer.get_pending_posts", return_value=[]):
            with patch("src.analyzer.analyze_post") as mock_analyze:
                result = run_analysis(max_rounds=5)
                mock_analyze.assert_not_called()
                assert result == 0


def test_run_analysis_max_rounds_limit():
    """Verify run_analysis strictly terminates when max_rounds limit is reached."""
    mock_post = ({"id": 1, "title": "Vídeo", "views": 100}, [])

    with patch("src.analyzer.load_config", return_value={"analysis": {}}):
        with patch("src.analyzer.get_pending_posts", return_value=[mock_post]) as mock_get:
            with patch("src.analyzer.analyze_post", return_value=True) as mock_analyze:
                with patch("src.analyzer.time.sleep") as mock_sleep:
                    result = run_analysis(max_rounds=3)
                    assert mock_get.call_count == 3
                    assert mock_analyze.call_count == 3
                    assert result == 3
                    assert mock_sleep.call_count == 2


def test_run_analysis_skips_failed_posts_in_subsequent_rounds():
    """Verify failing post is added to failed_post_ids and skipped in subsequent rounds."""
    post_failing = ({"id": 101, "title": "Failing Video", "views": 500}, [])

    def mock_get_pending(limit=20, exclude_ids=None):
        if exclude_ids and 101 in exclude_ids:
            return []
        return [post_failing]

    with patch("src.analyzer.load_config", return_value={"analysis": {}}):
        with patch("src.analyzer.get_pending_posts", side_effect=mock_get_pending) as mock_get:
            with patch("src.analyzer.analyze_post", return_value=False) as mock_analyze:
                with patch("src.analyzer.time.sleep"):
                    result = run_analysis(max_rounds=5)
                    # analyze_post should be called only ONCE for post 101
                    assert mock_analyze.call_count == 1
                    assert result == 0
                    assert mock_get.call_count == 2
                    second_call_exclude = mock_get.call_args_list[1].kwargs.get("exclude_ids")
                    assert 101 in second_call_exclude


def test_run_analysis_multi_round_success():
    """Verify run_analysis processes multi-round queue with mocked time.sleep until queue empties."""
    round1_posts = [
        ({"id": 1, "title": "V1", "views": 100}, []),
        ({"id": 2, "title": "V2", "views": 200}, []),
    ]
    round2_posts = [
        ({"id": 3, "title": "V3", "views": 300}, []),
    ]

    calls = [round1_posts, round2_posts, []]

    with patch("src.analyzer.load_config", return_value={"analysis": {}}):
        with patch("src.analyzer.get_pending_posts", side_effect=lambda limit=20, exclude_ids=None: calls.pop(0) if calls else []):
            with patch("src.analyzer.analyze_post", return_value=True) as mock_analyze:
                with patch("src.analyzer.time.sleep") as mock_sleep:
                    result = run_analysis(max_rounds=5)
                    assert mock_analyze.call_count == 3
                    assert result == 3
                    assert mock_sleep.call_count == 2


def test_get_pending_posts_with_exclude_ids():
    """Verify get_pending_posts constructs SQL with exclude_ids clause."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cur

    with patch("src.analyzer.get_connection", return_value=mock_conn):
        posts = get_pending_posts(limit=10, exclude_ids={101, 102})
        assert posts == []
        mock_cur.execute.assert_called_once()
        query, params = mock_cur.execute.call_args[0]
        assert "p.id != ALL(%s)" in query
        assert [101, 102] in params or [102, 101] in params or any(isinstance(p, list) and set(p) == {101, 102} for p in params)

