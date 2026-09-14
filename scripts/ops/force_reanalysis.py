import os
import sys
import psycopg2
from dotenv import load_dotenv

# Reconfigura o terminal para UTF-8 no Windows
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def force_reanalysis():
    if not DATABASE_URL:
        print("Erro: DATABASE_URL não configurada no .env")
        return

    print("Conectando ao banco de dados Supabase...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 1. Obter posts que possuem comentários coletados
        cur.execute("SELECT DISTINCT post_id FROM public.post_comments")
        posts_with_comments = [row[0] for row in cur.fetchall()]

        if not posts_with_comments:
            print("Nenhum post com comentários coletados foi encontrado no banco.")
            cur.close()
            conn.close()
            return

        print(f"Encontrados {len(posts_with_comments)} posts com comentários no banco.")

        # 2. Atualizar as análises de IA desses posts para public_sentiment = 'Inconclusivo'
        # Isso força o ai_video_analyzer.py a re-analisá-los usando a nova inteligência qualitativa comparativa.
        # Também setamos exported_to_zapier = FALSE para podermos exportá-los para Monday.com.
        query = """
            UPDATE public.post_ai_analysis
            SET public_sentiment = 'Inconclusivo',
                exported_to_zapier = FALSE
            WHERE post_id IN %s
        """
        cur.execute(query, (tuple(posts_with_comments),))
        rows_updated = cur.rowcount
        conn.commit()

        print(f"✓ Sucesso! {rows_updated} análises de IA foram marcadas como 'Inconclusivo' para forçar re-análise.")
        
        # 3. Mostrar status atual do banco
        cur.execute("SELECT COUNT(*) FROM public.post_ai_analysis WHERE LOWER(public_sentiment) LIKE '%inconclusiv%'")
        inconclusive_count = cur.fetchone()[0]
        print(f"Total de análises prontas para processamento pela IA (sentiment='Inconclusivo'): {inconclusive_count}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"✗ Erro ao atualizar banco: {e}")

if __name__ == "__main__":
    force_reanalysis()
