import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import requests
import yaml
from dotenv import load_dotenv

# Ensure the root of the project is in python path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from psycopg2.extras import RealDictCursor

from src.utils.db import get_connection

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
MONDAY_URL = "https://api.monday.com/v2"

def load_config(config_path=None):
    """Carrega a configuração do arquivo YAML especificado ou do padrão do piloto."""
    if not config_path:
        config_path = os.path.join(os.path.dirname(__file__), 'pilots', 'world_cup_2026', 'config.yaml')
        if not os.path.exists(config_path):
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
            
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# Global variables loaded from config
config = load_config()
# MONDAY_BOARD_ID can be overriden in config, fallback to pilot default
MONDAY_BOARD_ID = config.get('monday', {}).get('board_id', 18413482266)

SUBTOPIC_GROUP_MAP = {
    "figurinhas": "Figurinhas da Copa 2026",
    "tatica": "Tática e React de Jogos",
    "duvidas": "Drama e Especulação de Convocação",
    "polemicas": "Polêmicas da FIFA e Custos",
    "influencers": "Criadores em Ascensão"
}
DEFAULT_GROUP_TITLE = "Geral e Outros Temas"

def get_monday_headers():
    return {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
        "API-Version": "2023-10"
    }

def get_existing_monday_groups():
    """Busca os grupos existentes no board e retorna um mapa de {titulo_minusc: id}."""
    if not MONDAY_API_TOKEN:
        print("Erro: MONDAY_API_TOKEN não configurado!", file=sys.stderr)
        return {}
        
    query = """
    query ($boardId: [ID!]) {
      boards (ids: $boardId) {
        groups {
          id
          title
        }
      }
    }
    """
    try:
        resp = requests.post(
            MONDAY_URL, 
            json={"query": query, "variables": {"boardId": [str(MONDAY_BOARD_ID)]}}, 
            headers=get_monday_headers()
        )
        if resp.status_code == 200:
            data = resp.json()
            if "errors" in data:
                print(f"Erro ao buscar grupos: {data['errors']}", file=sys.stderr)
                return {}
            boards = data.get("data", {}).get("boards", [])
            if boards:
                groups = boards[0].get("groups", [])
                return {g["title"].strip().lower(): g["id"] for g in groups}
        else:
            print(f"Erro HTTP ao buscar grupos: {resp.status_code} - {resp.text}", file=sys.stderr)
    except Exception as e:
        print(f"Exceção ao buscar grupos da Monday: {e}", file=sys.stderr)
    return {}

def create_monday_group(group_title):
    """Cria um grupo no board e retorna o ID do grupo recém-criado."""
    if not MONDAY_API_TOKEN:
        return None
        
    query = """
    mutation ($boardId: ID!, $groupName: String!) {
      create_group (board_id: $boardId, group_name: $groupName) {
        id
      }
    }
    """
    try:
        resp = requests.post(
            MONDAY_URL, 
            json={"query": query, "variables": {"boardId": str(MONDAY_BOARD_ID), "groupName": group_title}}, 
            headers=get_monday_headers()
        )
        if resp.status_code == 200:
            data = resp.json()
            if "errors" in data:
                print(f"Erro ao criar grupo '{group_title}': {data['errors']}", file=sys.stderr)
                return None
            group_id = data.get("data", {}).get("create_group", {}).get("id")
            print(f"Grupo criado com sucesso na Monday: '{group_title}' -> ID: {group_id}", file=sys.stderr)
            return group_id
        else:
            print(f"Erro HTTP ao criar grupo: {resp.status_code} - {resp.text}", file=sys.stderr)
    except Exception as e:
        print(f"Exceção ao criar grupo na Monday: {e}", file=sys.stderr)
    return None

def extract_section(text, header, next_header=None):
    if not text:
        return "N/A"
    try:
        if header in text:
            parts = text.split(header)[1]
            if next_header and next_header in parts:
                parts = parts.split(next_header)[0]
            return parts.strip()
    except Exception as e:
        print(f"Erro ao extrair seção '{header}': {e}", file=sys.stderr)
    return text.strip()

def map_sentiment(sentiment_str):
    if not sentiment_str:
        return "Inconclusivo"
    s = sentiment_str.lower()
    if any(word in s for word in ["positiv", "sucesso", "bom", "ótimo", "gosta", "otimo"]):
        return "Positivo"
    if any(word in s for word in ["negativ", "crítica", "ruim", "péssim", "reclam", "critica", "pessim"]):
        return "Negativo"
    if any(word in s for word in ["neutr", "indiferente"]):
        return "Neutro"
    return "Inconclusivo"

def format_pain_points_and_sentiment(pain_points, sentiment_str):
    if isinstance(pain_points, list):
        pain_points_text = ", ".join(pain_points) if pain_points else "Nenhuma dor detectada"
    elif isinstance(pain_points, str):
        try:
            pp_list = json.loads(pain_points)
            if isinstance(pp_list, list):
                pain_points_text = ", ".join(pp_list) if pp_list else "Nenhuma dor detectada"
            else:
                pain_points_text = pain_points
        except:
            pain_points_text = pain_points if pain_points else "Nenhuma dor detectada"
    else:
        pain_points_text = "Nenhuma dor detectada"
        
    sentiment_detail = f" | Sentimento Detalhado: {sentiment_str}" if sentiment_str else ""
    combined_text = pain_points_text + sentiment_detail
    if len(combined_text) > 1900:
        combined_text = combined_text[:1897] + "..."
    return combined_text

def clean_string(val, max_len=255):
    if not val:
        return ""
    val_str = str(val).strip()
    if len(val_str) > max_len:
        val_str = val_str[:max_len-3] + "..."
    return val_str

def fetch_pending():
    if not DATABASE_URL:
        print(json.dumps({"error": "DATABASE_URL não configurado no .env"}))
        sys.exit(1)

    try:
        monday_groups = get_existing_monday_groups()
        print(f"Grupos carregados na Monday: {list(monday_groups.keys())}", file=sys.stderr)

        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT 
                p.id as post_id,
                p.content_title,
                p.post_url,
                p.views_count,
                p.likes_count,
                p.comments_count,
                p.subtopic,
                p.published_at,
                a.id as analysis_id,
                a.video_tone,
                a.editing_style,
                a.content_summary,
                a.audience_pain_points,
                a.public_sentiment,
                a.algorithm_relevance_score,
                a.strategic_insights
            FROM public.post_ai_analysis a
            JOIN public.social_posts p ON a.post_id = p.id
            WHERE a.exported_to_zapier = FALSE
            ORDER BY a.id ASC
            LIMIT 25
        """
        cur.execute(query)
        records = cur.fetchall()

        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                elif isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                return super().default(obj)

        formatted_records = []
        for r in records:
            post_id = r["post_id"]
            subtopic = r["subtopic"] or "geral"
            title = r["content_title"]
            
            target_group_title = SUBTOPIC_GROUP_MAP.get(subtopic.lower(), DEFAULT_GROUP_TITLE)
            target_key = target_group_title.strip().lower()
            
            if target_key in monday_groups:
                resolved_group_id = monday_groups[target_key]
            else:
                print(f"Grupo '{target_group_title}' não existe. Criando dinamicamente...", file=sys.stderr)
                new_group_id = create_monday_group(target_group_title)
                if new_group_id:
                    monday_groups[target_key] = new_group_id
                    resolved_group_id = new_group_id
                else:
                    resolved_group_id = "topics"
                    
            cur.execute("""
                SELECT author_name, comment_text, likes_count 
                FROM public.post_comments 
                WHERE post_id = %s 
                ORDER BY likes_count DESC 
                LIMIT 10
            """, (post_id,))
            top_comments = cur.fetchall()
            
            content_summary_text = r.get("content_summary") or ""
            strategic_insights_text = r.get("strategic_insights") or ""
            
            video_narrative = extract_section(content_summary_text, "--- NARRATIVA DO VÍDEO ---", "--- REAÇÃO DO PÚBLICO ---")
            public_reaction = extract_section(content_summary_text, "--- REAÇÃO DO PÚBLICO ---", "--- RESUMO GERAL ---")
            comparative_analysis = extract_section(strategic_insights_text, "--- ANÁLISE COMPARATIVA ---", "--- INSIGHTS ESTRATÉGICOS ---")
            
            update_body = f"""
            <h3>📊 ANÁLISE DE RELEVÂNCIA E COMENTÁRIOS</h3>
            <p><strong>Vídeo:</strong> {title}</p>
            <hr/>
            
            <h4>🔍 Comparação: Narrativa do Vídeo vs. Reação do Público</h4>
            <p><strong>Narrativa do Criador:</strong></p>
            <blockquote>{video_narrative}</blockquote>
            
            <p><strong>Reação da Audiência:</strong></p>
            <blockquote>{public_reaction}</blockquote>
            
            <p><strong>Análise Comparativa:</strong></p>
            <blockquote>{comparative_analysis}</blockquote>
            <hr/>
            
            <h4>💬 Top 10 Comentários Mais Curtidos (Coletores Oficiais)</h4>
            <ol>
            """
            
            if not top_comments:
                update_body += "<li>Nenhum comentário popular coletado via API oficial para este post.</li>"
            else:
                for c in top_comments:
                    author = c["author_name"]
                    text = c["comment_text"]
                    likes = c["likes_count"]
                    update_body += f"<li><strong>@{author}</strong> ({likes} curtidas):<br/><em>{text}</em></li><br/>"
                    
            update_body += "</ol>"
            
            clean_sentiment = map_sentiment(r.get("public_sentiment"))
            clean_pain_points = format_pain_points_and_sentiment(r.get("audience_pain_points"), r.get("public_sentiment"))
            clean_score = float(r.get("algorithm_relevance_score") or 0.0)
            clean_views = int(r.get("views_count") or 0)
            clean_tone = clean_string(r.get("video_tone"), 255)
            clean_editing = clean_string(r.get("editing_style"), 255)
            clean_url = str(r.get("post_url") or "https://youtube.com").strip()
            clean_title = clean_string(title, 255)

            rec_dict = dict(r)
            rec_dict["monday_group_id"] = resolved_group_id
            rec_dict["monday_update_body"] = update_body.strip()
            rec_dict["monday_sentiment_status"] = clean_sentiment
            rec_dict["monday_pain_points_text"] = clean_pain_points
            rec_dict["monday_views_count"] = clean_views
            rec_dict["monday_relevance_score"] = clean_score
            rec_dict["monday_video_tone"] = clean_tone
            rec_dict["monday_editing_style"] = clean_editing
            rec_dict["monday_post_url"] = clean_url
            rec_dict["monday_content_title"] = clean_title

            monday_cols = {
                "color_mm3dtq01": {"label": clean_sentiment},
                "numeric_mm3db5r3": clean_score,
                "text_mm3dmddk": clean_tone,
                "text_mm3d45gs": clean_pain_points,
                "text_mm3daj28": clean_editing,
                "numeric_mm3d5jsj": clean_views,
                "text_mm3da7sc": str(r.get("analysis_id")),
                "link_mm3drm8q": {"url": clean_url, "text": "Assistir no YouTube"}
            }
            rec_dict["monday_column_values"] = json.dumps(monday_cols, ensure_ascii=False)
            formatted_records.append(rec_dict)

        print(json.dumps(formatted_records, cls=CustomEncoder, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": f"Falha na conexão ou busca: {e!s}"}))
        sys.exit(1)
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    fetch_pending()
