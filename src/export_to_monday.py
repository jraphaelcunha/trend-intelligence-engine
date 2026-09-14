import json
import os
import sys

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# Reconfigura o terminal para UTF-8 no Windows
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
MONDAY_BOARD_ID = 18413482266
MONDAY_URL = "https://api.monday.com/v2"

# Import helpers from fetcher
sys.path.append(os.path.dirname(__file__))
from src.fetcher import (
    DEFAULT_GROUP_TITLE,
    SUBTOPIC_GROUP_MAP,
    create_monday_group,
    extract_section,
    format_pain_points_and_sentiment,
    get_existing_monday_groups,
    map_sentiment,
)


def get_monday_headers():
    return {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
        "API-Version": "2023-10"
    }

def run_export():
    print("="*60)
    print("🚀 INICIANDO EXPORTAÇÃO DIRETA DE DOSSIÊS PARA MONDAY.COM")
    print("="*60)
    
    if not MONDAY_API_TOKEN:
        print("❌ Erro: MONDAY_API_TOKEN não configurado no .env!")
        return

    try:
        # 1. Carrega os grupos da Monday
        print("📂 Buscando grupos existentes no Monday...")
        monday_groups = get_existing_monday_groups()
        print(f"Grupos carregados na Monday: {list(monday_groups.keys())}\n")

        # 2. Carrega as análises pendentes no banco
        print("🔌 Conectando ao banco de dados Supabase...")
        conn = psycopg2.connect(DATABASE_URL)
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
        """
        cur.execute(query)
        records = cur.fetchall()

        if not records:
            print("✅ Nenhuma análise pendente de exportação no banco!")
            return

        print(f"📋 Encontradas {len(records)} análises pendentes de exportação.\n")

        success_count = 0
        for idx, r in enumerate(records, 1):
            post_id = r["post_id"]
            analysis_id = r["analysis_id"]
            subtopic = r["subtopic"] or "geral"
            title = r["content_title"]

            print(f"[{idx}/{len(records)}] 🎬 Processando: {title[:50]}...")

            # --- RESOLUÇÃO DO GRUPO DA MONDAY.COM ---
            target_group_title = SUBTOPIC_GROUP_MAP.get(subtopic.lower(), DEFAULT_GROUP_TITLE)
            target_key = target_group_title.strip().lower()
            
            if target_key in monday_groups:
                resolved_group_id = monday_groups[target_key]
            else:
                # Criar dinamicamente o grupo na Monday
                print(f"  📂 Grupo '{target_group_title}' não existe. Criando dinamicamente...")
                new_group_id = create_monday_group(target_group_title)
                if new_group_id:
                    monday_groups[target_key] = new_group_id
                    resolved_group_id = new_group_id
                else:
                    resolved_group_id = "topics" # fallback
                    print("  ⚠️ Falha ao criar grupo, usando fallback 'topics'")

            # --- BUSCA DOS TOP 10 COMENTÁRIOS DO VÍDEO ---
            cur.execute("""
                SELECT author_name, comment_text, likes_count 
                FROM public.post_comments 
                WHERE post_id = %s 
                ORDER BY likes_count DESC 
                LIMIT 10
            """, (post_id,))
            top_comments = cur.fetchall()

            # --- PARSE DAS SEÇÕES DA ANÁLISE DE IA ---
            content_summary_text = r.get("content_summary") or ""
            strategic_insights_text = r.get("strategic_insights") or ""
            
            video_narrative = extract_section(content_summary_text, "--- NARRATIVA DO VÍDEO ---", "--- REAÇÃO DO PÚBLICO ---")
            public_reaction = extract_section(content_summary_text, "--- REAÇÃO DO PÚBLICO ---", "--- RESUMO GERAL ---")
            comparative_analysis = extract_section(strategic_insights_text, "--- ANÁLISE COMPARATIVA ---", "--- INSIGHTS ESTRATÉGICOS ---")

            # --- FORMATAÇÃO DO TEXTO DO UPDATE DA MONDAY ---
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

            # --- FORMATAÇÃO DAS COLUNAS DA SPREADSHEET ---
            clean_sentiment = map_sentiment(r.get("public_sentiment"))
            clean_pain_points = format_pain_points_and_sentiment(r.get("audience_pain_points"), r.get("public_sentiment"))
            clean_score = float(r.get("algorithm_relevance_score") or 0.0)
            clean_views = int(r.get("views_count") or 0)
            clean_tone = clean_string(r.get("video_tone"), 255)
            clean_editing = clean_string(r.get("editing_style"), 255)
            clean_url = str(r.get("post_url") or "https://youtube.com").strip()
            clean_title = clean_string(title, 255)

            monday_cols = {
                "color_mm3dtq01": {"label": clean_sentiment},
                "numeric_mm3db5r3": clean_score,
                "text_mm3dmddk": clean_tone,
                "text_mm3d45gs": clean_pain_points,
                "text_mm3daj28": clean_editing,
                "numeric_mm3d5jsj": clean_views,
                "text_mm3da7sc": str(analysis_id),
                "link_mm3drm8q": {"url": clean_url, "text": "Assistir no YouTube"}
            }

            # 3. Criar Item na Monday
            print("  ➕ Criando item na planilha do Monday...")
            create_item_query = """
            mutation ($boardId: ID!, $groupId: String!, $itemName: String!, $columnValues: JSON!) {
              create_item (board_id: $boardId, group_id: $groupId, item_name: $itemName, column_values: $columnValues, create_labels_if_missing: true) {
                id
              }
            }
            """
            
            payload = {
                "query": create_item_query,
                "variables": {
                    "boardId": str(MONDAY_BOARD_ID),
                    "groupId": resolved_group_id,
                    "itemName": clean_title,
                    "columnValues": json.dumps(monday_cols)
                }
            }
            
            resp_item = requests.post(MONDAY_URL, json=payload, headers=get_monday_headers())
            if resp_item.status_code != 200:
                print(f"  ❌ Erro HTTP ao criar item: {resp_item.status_code} - {resp_item.text}")
                continue
                
            res_item_data = resp_item.json()
            if "errors" in res_item_data:
                print(f"  ❌ Erro da API do Monday ao criar item: {res_item_data['errors']}")
                continue
                
            item_id = res_item_data.get("data", {}).get("create_item", {}).get("id")
            if not item_id:
                print("  ❌ Item ID não encontrado na resposta.")
                continue

            print(f"  ✓ Item criado com sucesso (ID: {item_id})!")

            # 4. Criar Update na Monday (rich-text)
            print("  💬 Postando análise comparativa e top comentários no balão do item...")
            create_update_query = """
            mutation ($itemId: ID!, $body: String!) {
              create_update (item_id: $itemId, body: $body) {
                id
              }
            }
            """
            
            payload_update = {
                "query": create_update_query,
                "variables": {
                    "itemId": str(item_id),
                    "body": update_body.strip()
                }
            }
            
            resp_update = requests.post(MONDAY_URL, json=payload_update, headers=get_monday_headers())
            if resp_update.status_code != 200:
                print(f"  ⚠️ Erro HTTP ao postar update: {resp_update.status_code}")
            else:
                res_update_data = resp_update.json()
                if "errors" in res_update_data:
                    print(f"  ⚠️ Erve da API do Monday ao postar update: {res_update_data['errors']}")
                else:
                    print("  ✓ Balão de atualização postado com sucesso!")

            # 5. Marcar como exportado no Supabase
            cur.execute("UPDATE public.post_ai_analysis SET exported_to_zapier = TRUE WHERE id = %s", (analysis_id,))
            conn.commit()
            print("  ✓ Sucesso! Post marcado como exportado no Supabase.\n")
            success_count += 1

        print("="*60)
        print(f"✅ EXPORTAÇÃO FINALIZADA! {success_count}/{len(records)} posts exportados com sucesso.")
        print("="*60)

    except Exception as e:
        print(f"❌ Ocorreu uma exceção: {e}")
    finally:
        if 'cur' in locals() and cur: cur.close()
        if 'conn' in locals() and conn: conn.close()

if __name__ == "__main__":
    run_export()
