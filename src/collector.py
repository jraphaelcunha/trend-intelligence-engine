import datetime
import os
import sys

import yaml
from dotenv import load_dotenv
from googleapiclient.discovery import build

# Ensure the root of the project is in python path for absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from psycopg2.extras import execute_values

from src.utils.db import get_connection

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None

def load_config(config_path=None):
    """Carrega a configuração do arquivo YAML especificado ou do padrão do piloto."""
    if not config_path:
        # Fallback para o piloto padrão se não fornecido
        config_path = os.path.join(os.path.dirname(__file__), 'pilots', 'world_cup_2026', 'config.yaml')
        if not os.path.exists(config_path):
            # Fallback para a raiz se o piloto não existir
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
            
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def search_youtube_videos(query, subtopic_id, config, max_results=10, order='viewCount', published_after=None, region_code='BR', language='pt'):
    """
    Busca vídeos no YouTube pela palavra-chave.
    Filtra por data de publicação, região e idioma.
    """
    if not youtube:
        raise ValueError("YOUTUBE_API_KEY não configurada de forma válida.")

    print(f"  🔍 Buscando: '{query}' (ordem: {order}, região: {region_code})...")
    
    search_params = {
        'q': query,
        'part': 'id,snippet',
        'type': 'video',
        'order': order,
        'maxResults': max_results,
        'relevanceLanguage': language,
        'regionCode': region_code
    }
    
    if published_after:
        search_params['publishedAfter'] = published_after + 'T00:00:00Z'
    
    search_response = youtube.search().list(**search_params).execute()
    
    videos_data = []
    video_ids = [item['id']['videoId'] for item in search_response.get('items', []) if item['id'].get('videoId')]
    
    if not video_ids:
        print(f"  ⚠️ Nenhum vídeo encontrado para: '{query}'")
        return []
    
    # Buscar estatísticas em lote (1 chamada de API em vez de N)
    stats_response = youtube.videos().list(
        id=','.join(video_ids),
        part='statistics'
    ).execute()
    
    stats_map = {}
    for item in stats_response.get('items', []):
        stats_map[item['id']] = item['statistics']
    
    for search_result in search_response.get('items', []):
        video_id = search_result['id'].get('videoId')
        if not video_id:
            continue
            
        snippet = search_result['snippet']
        stats = stats_map.get(video_id, {})
        
        views = int(stats.get('viewCount', 0))
        comments = int(stats.get('commentCount', 0))
        likes = int(stats.get('likeCount', 0))
        
        # Filtros de Engajamento e Tempo baseados no config
        search_cfg = config.get('search', {})
        min_views = search_cfg.get('min_views', 0)
        min_ratio = search_cfg.get('min_engagement_ratio', 0.0)
        
        # Calcular tempo de lançamento do vídeo em dias
        try:
            pub_str = snippet['publishedAt'].replace('Z', '+00:00')
            published_dt = datetime.datetime.fromisoformat(pub_str)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            time_diff = now_dt - published_dt
            days_elapsed = time_diff.total_seconds() / 86400.0
            if days_elapsed <= 0:
                days_elapsed = 0.04  # Cerca de 1 hora mínimo para evitar divisão por zero
        except Exception as te:
            print(f"  ⚠️ Erro ao calcular data do vídeo {video_id}: {te}")
            days_elapsed = 1.0

        views_per_day = views / days_elapsed
        
        adv = search_cfg.get('advanced_metrics', {})
        if adv.get('enabled', False):
            recent_days = adv.get('recent_video_days', 7)
            recent_min_views = adv.get('recent_min_views', 5000)
            min_views_per_day = adv.get('min_views_per_day', 1500)
            recent_min_views_per_day = adv.get('recent_min_views_per_day', 700)
            
            is_recent = days_elapsed <= recent_days
            
            if is_recent:
                if views < recent_min_views:
                    print(f"  ⏭️ Vídeo recente '{snippet['title'][:30]}...' ignorado: views ({views}) < {recent_min_views}")
                    continue
                if views_per_day < recent_min_views_per_day:
                    print(f"  ⏭️ Vídeo recente '{snippet['title'][:30]}...' ignorado: views/dia ({views_per_day:.1f}) < {recent_min_views_per_day}")
                    continue
            else:
                if views < min_views:
                    print(f"  ⏭️ Vídeo antigo '{snippet['title'][:30]}...' ignorado: views ({views}) < {min_views}")
                    continue
                if views_per_day < min_views_per_day:
                    print(f"  ⏭️ Vídeo antigo '{snippet['title'][:30]}...' ignorado: views/dia ({views_per_day:.1f}) < {min_views_per_day}")
                    continue
        else:
            if views < min_views:
                continue
            
        ratio = (comments / views) if views > 0 else 0
        if ratio < min_ratio:
            print(f"  ⏭️ Vídeo '{snippet['title'][:30]}...' ignorado por baixo engajamento: ratio ({ratio:.4f}) < {min_ratio}")
            continue
            
        video_data = {
            "platform": "youtube",
            "post_url": f"https://www.youtube.com/watch?v={video_id}",
            "author_name": snippet['channelTitle'],
            "author_handle": snippet['channelId'],
            "content_title": snippet['title'],
            "content_description": snippet['description'],
            "published_at": snippet['publishedAt'],
            "views_count": views,
            "likes_count": likes,
            "comments_count": comments,
            "subtopic": subtopic_id,
            "scraped_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        videos_data.append(video_data)
        
    return videos_data

def save_to_database(videos):
    """Salva os vídeos no Supabase. Evita duplicações via ON CONFLICT."""
    if not videos:
        print("  Nenhum vídeo para salvar.")
        return 0

    try:
        conn = get_connection()
        conn.autocommit = True
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO public.social_posts (
                platform, post_url, author_name, author_handle, 
                content_title, content_description, published_at, 
                views_count, likes_count, comments_count, subtopic, scraped_at
            ) VALUES %s
            ON CONFLICT (post_url) DO UPDATE SET
                views_count = EXCLUDED.views_count,
                likes_count = EXCLUDED.likes_count,
                comments_count = EXCLUDED.comments_count;
        """

        values_to_insert = [
            (
                v["platform"], v["post_url"], v["author_name"], v["author_handle"],
                v["content_title"], v["content_description"], v["published_at"],
                v["views_count"], v["likes_count"], v["comments_count"],
                v["subtopic"], v["scraped_at"]
            )
            for v in videos
        ]

        execute_values(cursor, insert_query, values_to_insert)
        print(f"  ✅ {len(videos)} vídeos processados no banco (inseridos/atualizados).")
        return len(videos)

    except Exception as e:
        print(f"  ❌ Erro ao salvar no banco: {e}")
        return 0
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def run_collection(config_path=None):
    """Executa a coleta completa baseada no config.yaml."""
    config = load_config(config_path)
    theme = config['theme']['name']
    search_cfg = config['search']
    subtopics = config['subtopics']
    
    print(f"{'='*60}")
    print("🏆 TREND INTELLIGENCE ENGINE — COLLECTOR")
    print(f"📌 Tema: {theme}")
    print(f"📅 Buscando desde: {search_cfg['date_start']}")
    print(f"📊 Top {search_cfg['max_videos_per_subtopic']} por sub-tema")
    print(f"{'='*60}\n")
    
    total_videos = 0
    
    for region in search_cfg['regions']:
        print(f"\n🌎 Região: {region['label']} ({region['code']})")
        print(f"{'-'*40}")
        
        for subtopic in subtopics:
            print(f"\n📂 Sub-Tema: {subtopic['name']}")
            
            subtopic_videos = []
            for keyword in subtopic['keywords']:
                results = search_youtube_videos(
                    query=keyword,
                    subtopic_id=subtopic['id'],
                    config=config,
                    max_results=search_cfg['max_videos_per_subtopic'],
                    order=search_cfg['order_by'],
                    published_after=search_cfg['date_start'],
                    region_code=region['code'],
                    language=region['language']
                )
                subtopic_videos.extend(results)
            
            seen_urls = set()
            unique_videos = []
            for v in subtopic_videos:
                if v['post_url'] not in seen_urls:
                    seen_urls.add(v['post_url'])
                    unique_videos.append(v)
            
            saved = save_to_database(unique_videos)
            total_videos += saved
            print(f"  📊 {len(unique_videos)} únicos encontrados, {saved} processados no banco.")
    
    print(f"\n{'='*60}")
    print("✅ COLETA FINALIZADA!")
    print(f"📊 Total de vídeos processados: {total_videos}")
    print(f"{'='*60}")

if __name__ == "__main__":
    if not YOUTUBE_API_KEY or "COLE_SUA_CHAVE" in YOUTUBE_API_KEY:
        print("ALERTA: Configurar a YOUTUBE_API_KEY no arquivo .env!")
    else:
        run_collection()
