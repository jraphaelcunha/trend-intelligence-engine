import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def check_status():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 1. Total social posts
        cur.execute("SELECT COUNT(*) FROM public.social_posts")
        total_posts = cur.fetchone()[0]

        # 2. Total analyses
        cur.execute("SELECT COUNT(*) FROM public.post_ai_analysis")
        total_analyses = cur.fetchone()[0]

        # 3. Exported vs pending
        cur.execute("SELECT COUNT(*) FROM public.post_ai_analysis WHERE exported_to_zapier = TRUE")
        exported = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM public.post_ai_analysis WHERE exported_to_zapier = FALSE")
        pending = cur.fetchone()[0]

        print("=== DATABASE STATUS ===")
        print(f"Total social posts: {total_posts}")
        print(f"Total AI analyses: {total_analyses}")
        print(f"  - Exported to Monday: {exported}")
        print(f"  - Pending export: {pending}")

        if pending > 0:
            cur.execute("""
                SELECT p.content_title, a.public_sentiment, a.algorithm_relevance_score
                FROM public.post_ai_analysis a
                JOIN public.social_posts p ON a.post_id = p.id
                WHERE a.exported_to_zapier = FALSE
                LIMIT 5
            """)
            print("\nPending samples:")
            for row in cur.fetchall():
                print(f"  - Title: {row[0][:50]}...")
                print(f"    Sentiment: {row[1]}")
                print(f"    Score: {row[2]}")
        else:
            print("\nNo pending exports.")

        cur.close()
        conn.close()

    except Exception as e:
        print("Erro:", e)

if __name__ == "__main__":
    check_status()
