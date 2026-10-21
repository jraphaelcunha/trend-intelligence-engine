"""
Unit tests for analyzer module, prompt construction, dual-sampling, and database persistence.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.analyzer import (
    analyze_post,
    extract_video_id,
    get_subtopic_context,
    get_transcript,
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
            save_analysis(post_id=42, analysis_json=analysis_data, existing_analysis_id=999)
            mock_cur.execute.assert_called_once()
            assert "UPDATE public.post_ai_analysis" in mock_cur.execute.call_args[0][0]
            mock_conn.close.assert_called_once()
