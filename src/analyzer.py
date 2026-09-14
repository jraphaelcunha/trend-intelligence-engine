import json
import os
import sys

import google.generativeai as genai
import yaml
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

# Ensure the root of the project is in python path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils.db import get_connection

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def load_config(config_path=None):
    """Carrega a configuração do arquivo YAML especificado ou do padrão do piloto."""
    if not config_path:
        # Fallback para o piloto padrão se não fornecido
        config_path = os.path.join(os.path.dirname(__file__), 'pilots', 'world_cup_2026', 'config.yaml')
        if not os.path.exists(config_path):
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
            
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# Global variables loaded from config
config = load_config()
model_name = config.get('analysis', {}).get('model', 'gemini-2.5-flash')
model = genai.GenerativeModel(model_name)

def extract_video_id(url):
    """Extrai o ID do vídeo de uma URL do YouTube."""
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return None

def get_transcript(video_id):
    """Obtém a transcrição do vídeo via youtube-transcript-api."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'en', 'pt-BR'])
        full_text = " ".join([item['text'] for item in transcript_list])
        return full_text
    except Exception as e:
        print(f"  ⚠️ Legenda indisponível para {video_id}: {type(e).__name__}")
        return "Legenda indisponível."

def get_subtopic_context(subtopic_id, active_config):
    """Retorna o contexto de análise específico para o sub-tema."""
    for st in active_config.get('subtopics', []):
        if st['id'] == subtopic_id:
            return st.get('name', ''), st.get('analysis_angle', '')
    return '', ''

def get_pending_posts(limit=10):
    """Pega posts que ainda não têm análise de IA ou cuja análise anterior deu Inconclusivo, priorizando views."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT p.id, p.post_url, p.content_title, p.content_description, 
                   p.views_count, p.likes_count, p.subtopic, a.id as analysis_id
            FROM public.social_posts p
            LEFT JOIN public.post_ai_analysis a ON p.id = a.post_id
            WHERE a.id IS NULL OR LOWER(a.public_sentiment) LIKE '%%inconclusiv%%'
            ORDER BY p.views_count DESC
            LIMIT %s;
        """
        cursor.execute(query, (limit,))
        posts = cursor.fetchall()
        
        result = []
        for post in posts:
            post_data = {
                "id": post[0],
                "url": post[1],
                "title": post[2],
                "description": post[3],
                "views": post[4],
                "likes": post[5],
                "subtopic": post[6],
                "existing_analysis_id": post[7]
            }
            
            cursor.execute("""
                SELECT author_name, comment_text, likes_count 
                FROM public.post_comments 
                WHERE post_id = %s 
                ORDER BY likes_count DESC;
            """, (post[0],))
            comments = cursor.fetchall()
            comments_data = [{"author": c[0], "text": c[1], "likes": c[2]} for c in comments]
            
            result.append((post_data, comments_data))
        
        return result
        
    except Exception as e:
        print(f"Erro no banco ao carregar posts: {e}")
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def save_analysis(post_id, analysis_json, existing_analysis_id=None):
    """Salva ou atualiza a análise no banco com embeddings."""
    try:
        video_narrative = analysis_json.get("video_narrative", "N/A")
        public_reaction = analysis_json.get("public_reaction", "N/A")
        content_summary = analysis_json.get("content_summary", "N/A")
        
        rich_summary = f"""--- NARRATIVA DO VÍDEO ---
{video_narrative}

--- REAÇÃO DO PÚBLICO ---
{public_reaction}

--- RESUMO GERAL ---
{content_summary}"""

        narrative_vs_reaction = analysis_json.get("narrative_vs_reaction", "N/A")
        strategic_insights = analysis_json.get("strategic_insights", "N/A")
        
        rich_insights = f"""--- ANÁLISE COMPARATIVA ---
{narrative_vs_reaction}

--- INSIGHTS ESTRATÉGICOS ---
{strategic_insights}"""

        texto_para_embedding = f"""
        Tom do Vídeo: {analysis_json.get('video_tone', '')}
        Estilo de Edição: {analysis_json.get('editing_style', '')}
        Resumo: {rich_summary}
        Dores do Público: {', '.join(analysis_json.get('audience_pain_points', []))}
        Insights Estratégicos: {rich_insights}
        """
        
        print("  🧠 Gerando Embedding Vetorial para o RAG...")
        embed_result = genai.embed_content(
            model="models/gemini-embedding-2",
            content=texto_para_embedding
        )
        embedding_vector = embed_result['embedding']

        conn = get_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        pain_points = analysis_json.get("audience_pain_points", [])
        if isinstance(pain_points, str):
            pain_points = [pain_points]
            
        public_sentiment = analysis_json.get("public_sentiment", "Neutro")
        
        if existing_analysis_id:
            query = """
                UPDATE public.post_ai_analysis
                SET video_tone = %s, editing_style = %s, content_summary = %s, 
                    audience_pain_points = %s, public_sentiment = %s, 
                    algorithm_relevance_score = %s, strategic_insights = %s, 
                    embedding = %s, analyzed_at = NOW(), exported_to_zapier = FALSE
                WHERE id = %s
            """
            values = (
                analysis_json.get("video_tone", "N/A")[:100],
                analysis_json.get("editing_style", "N/A"),
                rich_summary,
                pain_points,
                public_sentiment[:50],
                float(analysis_json.get("algorithm_relevance_score", 0.0)),
                rich_insights,
                embedding_vector,
                existing_analysis_id
            )
            cursor.execute(query, values)
            print(f"  ✅ Dossiê de Relevância ATUALIZADO no banco (ID: {existing_analysis_id})!")
        else:
            query = """
                INSERT INTO public.post_ai_analysis (
                    post_id, video_tone, editing_style, content_summary, 
                    audience_pain_points, public_sentiment, 
                    algorithm_relevance_score, strategic_insights, embedding, exported_to_zapier
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
            """
            values = (
                post_id,
                analysis_json.get("video_tone", "N/A")[:100],
                analysis_json.get("editing_style", "N/A"),
                rich_summary,
                pain_points,
                public_sentiment[:50],
                float(analysis_json.get("algorithm_relevance_score", 0.0)),
                rich_insights,
                embedding_vector
            )
            cursor.execute(query, values)
            print("  ✅ Novo Dossiê e Vetores salvos no banco!")
            
    except Exception as e:
        print(f"  ❌ Erro ao salvar análise ou embedding: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def analyze_post(post, comments, active_config):
    """Analisa um post individual com foco na comparação entre Narrativa do Vídeo e Reação do Público."""
    subtopic_name, analysis_angle = get_subtopic_context(post.get('subtopic'), active_config)
    base_context = active_config.get('analysis', {}).get('base_context', '')
    
    video_id = extract_video_id(post['url'])
    transcript = get_transcript(video_id)
    
    top_10 = comments[:10]
    sample_100 = comments[:100]
    
    prompt = f"""
    {base_context}
    
    SUB-TEMA ESPECÍFICO: {subtopic_name}
    ÂNGULO DE ANÁLISE: {analysis_angle}
    
    METADADOS DO VÍDEO:
    - Título: {post['title']}
    - Descrição: {post['description'][:1000]}
    
    TRANSCRIÇÃO COMPLETA DO VÍDEO:
    "{transcript[:15000]}"
    
    --- DADOS DE COMENTÁRIOS DO PÚBLICO ---
    
    PRINCIPAIS 10 COMENTÁRIOS MAIS CURTIDOS (Foco Qualitativo Profundo):
    {json.dumps(top_10, ensure_ascii=False, indent=2)}
    
    AMOSTRA DOS 100 PRIMEIROS COMENTÁRIOS PARA ANÁLISE DE TENDÊNCIA E DENSIDADE:
    {json.dumps([c.get('text', '')[:150] for c in sample_100], ensure_ascii=False)}
    
    Com base em todos os dados acima, faça uma análise crítica profunda sobre a recepção do vídeo. 
    Seu foco principal é construir uma comparação clara e sincera entre a Narrativa do Vídeo (o que o criador defende) e a Reação do Público (como a audiência responde nos comentários).
    
    Retorne ESTRITAMENTE um JSON válido no formato abaixo, sem texto antes ou depois:
    {{
        "video_tone": "Como o criador embala a narrativa (ex: Denúncia, Deboche, Técnico, Alarmista, Fofoca)",
        "editing_style": "Formato e padrão visual do criador (ex: React com cortes rápidos, Podcast estático, Vlog de alta retenção)",
        "content_summary": "Resumo objetivo e dinâmico sobre a principal tese do criador no vídeo.",
        
        "video_narrative": "Discorra em 2-3 parágrafos curtos sobre o que o vídeo de fato diz: qual a tese defendida pelo criador, a novidade revelada e a narrativa que ele tenta emplacar para prender o público.",
        "public_reaction": "Discorra em 2-3 parágrafos curtos sobre qual é a reação real do público baseado nos comentários coletados. Eles compram a briga? Trazem argumentos contrários? Apontam mentiras ou trazem piadas/deboches?",
        "narrative_vs_reaction": "Uma declaração analítica comparando diretamente a Narrativa do Criador com a Reação da Audiência. Aponte se há alinhamento, atrito, ceticismo geral ou se o público está focado em algo totalmente diferente do que o vídeo propõe.",
        
        "audience_pain_points": [
            "Dor, costume ou opinião 1 do público identificada nas conversas",
            "Dor, costume ou opinião 2 do público identificada nas conversas"
        ],
        "public_sentiment": "Classifique obrigatoriamente em apenas uma das três palavras: 'Positivo', 'Negativo' ou 'Neutro'. Baseie-se na tendência de recepção da audiência. Nunca retorne 'Inconclusivo'.",
        "algorithm_relevance_score": 8.5,
        "strategic_insights": "Qual o insight estratégico que nós, como marcas ou produtores concorrentes, tiramos disso? Como podemos nos posicionar diante deste contraste detectado?"
    }}
    
    NÃO inclua nenhuma marcação ```json, retorne apenas a string JSON pura.
    """
    
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        raw_text = raw_text.removeprefix('```json')
        raw_text = raw_text.removeprefix('```')
        raw_text = raw_text.removesuffix('```')
            
        analysis_result = json.loads(raw_text.strip())
        
        sentiment = analysis_result.get('public_sentiment', 'Neutro').strip()
        if sentiment not in ["Positivo", "Negativo", "Neutro"]:
            analysis_result['public_sentiment'] = "Neutro"
            
        print(f"  📊 Tom: {analysis_result.get('video_tone')} | Sentimento: {analysis_result.get('public_sentiment')} | Score: {analysis_result.get('algorithm_relevance_score')}")
        
        save_analysis(post['id'], analysis_result, post.get("existing_analysis_id"))
        return True
        
    except Exception as e:
        print(f"  ❌ Erro ao processar IA para o post {post['id']}: {e}")
        return False

def run_analysis(config_path=None):
    active_config = load_config(config_path)
    active_model_name = active_config.get('analysis', {}).get('model', 'gemini-2.5-flash')
    
    print(f"{'='*60}")
    print("🧠 MÓDULO DE IA ESTRATÉGICA - ANALYZER")
    print(f"🤖 Modelo: {active_model_name}")
    print(f"{'='*60}\n")
    
    round_count = 1
    while True:
        print(f"🔄 Iniciando Rodada {round_count}...")
        pending = get_pending_posts(limit=20)
        
        if not pending:
            print("✅ Todos os posts já possuem análises ricas e concluídas!")
            break
            
        print(f"📋 Encontrados {len(pending)} posts pendentes ou que precisam de re-análise nesta rodada.\n")
        
        success = 0
        for i, (post, comments) in enumerate(pending, 1):
            print(f"[{i}/{len(pending)}] 🎬 {post['title'][:60]}...")
            print(f"  📂 Sub-tema: {post.get('subtopic', 'geral')} | 👁️ {post['views']} views | 💬 {len(comments)} comentários coletados")
            
            if analyze_post(post, comments, active_config):
                success += 1
            sys.stdout.flush()
                
        print(f"\nRodada {round_count} concluída. Processados com sucesso: {success}/{len(pending)}")
        print(f"{'-'*60}\n")
        sys.stdout.flush()
        round_count += 1
        time.sleep(2)

if __name__ == "__main__":
    run_analysis()
