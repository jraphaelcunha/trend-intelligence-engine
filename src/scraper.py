import datetime
import os
import sys
import time

from dotenv import load_dotenv
from googleapiclient.discovery import build

# Ensure the root of the project is in python path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from psycopg2.extras import execute_values

from src.utils.db import get_connection

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
if not YOUTUBE_API_KEY:
    print("Erro: YOUTUBE_API_KEY não configurada no arquivo .env!")
    sys.exit(1)

# Inicializar cliente do YouTube API
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, static_discovery=False)

def extract_video_id(url):
    """Extrai o ID do vídeo de uma URL do YouTube."""
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return None

def get_videos_needing_comments():
    """Busca no banco de dados vídeos que ainda não possuem comentários coletados."""
    print("Buscando vídeos que precisam de comentários no banco de dados...")
    videos = []
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT id, post_url 
            FROM public.social_posts 
            WHERE id NOT IN (SELECT DISTINCT post_id FROM public.post_comments)
            ORDER BY views_count DESC;
        """
        cursor.execute(query)
        videos = cursor.fetchall()
    except Exception as e:
        print(f"Erro ao buscar vídeos no banco: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
    return videos

def fetch_comments_via_api(video_id, max_results=100):
    """Obtém os comentários mais populares do vídeo usando a API oficial do YouTube."""
    comments = []
    try:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            order="relevance",
            textFormat="plainText"
        ).execute()
        
        for item in response.get("items", []):
            top_comment = item["snippet"]["topLevelComment"]
            snippet = top_comment["snippet"]
            
            pub_at = snippet.get("publishedAt")
            
            comments.append({
                "author_name": snippet.get("authorDisplayName", "Anônimo"),
                "comment_text": snippet.get("textDisplay", ""),
                "likes_count": int(snippet.get("likeCount", 0)),
                "published_at": pub_at
            })
    except Exception as e:
        err_msg = str(e)
        if "commentsDisabled" in err_msg:
            print(f"  ⚠️ Comentários desativados para o vídeo ID {video_id}")
        else:
            print(f"  ⚠️ Erro ao buscar comentários da API para o vídeo {video_id}: {e}")
    return comments

def save_comments_to_db(post_id, comments_data):
    """Salva os comentários extraídos na tabela post_comments de forma limpa."""
    if not comments_data:
        return
        
    try:
        conn = get_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 1. Limpa comentários antigos desse post para evitar duplicidades
        cursor.execute("DELETE FROM public.post_comments WHERE post_id = %s", (post_id,))
        
        # 2. Insere os novos comentários
        insert_query = """
            INSERT INTO public.post_comments (
                post_id, author_name, comment_text, likes_count, published_at, scraped_at
            ) VALUES %s
        """
        
        values_to_insert = [
            (
                post_id, 
                c["author_name"], 
                c["comment_text"], 
                c["likes_count"], 
                c["published_at"],
                datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
            for c in comments_data
        ]
        
        execute_values(cursor, insert_query, values_to_insert)
        print(f"  ✅ Salvos {len(comments_data)} comentários para o vídeo no banco de dados!")
    except Exception as e:
        print(f"  ❌ Erro ao salvar comentários no banco: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def run_comment_scraper():
    print("=== INICIANDO COLETA DE COMENTÁRIOS VIA YOUTUBE API ===")
    videos = get_videos_needing_comments()
    
    if not videos:
        print("Nenhum vídeo pendente de coleta de comentários encontrado.")
        return
        
    print(f"Encontrados {len(videos)} vídeos que precisam de comentários.")
    
    success_count = 0
    for idx, (post_id, post_url) in enumerate(videos):
        video_id = extract_video_id(post_url)
        if not video_id:
            print(f"[{idx+1}/{len(videos)}] URL de vídeo inválida: {post_url}")
            continue
            
        print(f"[{idx+1}/{len(videos)}] Coletando comentários do vídeo ID: {video_id} ({post_url})")
        
        comments = fetch_comments_via_api(video_id, max_results=100)
        
        if comments:
            save_comments_to_db(post_id, comments)
            success_count += 1
        else:
            print(f"  ⚠️ Nenhum comentário retornado para o vídeo {video_id}")
            
        time.sleep(0.5)
        
    print(f"\n=== COLETA DE COMENTÁRIOS CONCLUÍDA: {success_count}/{len(videos)} vídeos processados ===")

if __name__ == "__main__":
    run_comment_scraper()
