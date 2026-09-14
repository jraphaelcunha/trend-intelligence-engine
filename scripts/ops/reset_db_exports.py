import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def reset_all_exports():
    if not DATABASE_URL:
        print("Erro: DATABASE_URL não configurado no .env")
        return

    print("Conectando ao banco de dados Supabase...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Atualizar todas as análises de IA para FALSE
        query = "UPDATE public.post_ai_analysis SET exported_to_zapier = FALSE"
        cur.execute(query)
        rows_updated = cur.rowcount
        conn.commit()

        print(f"✓ Sucesso! Todas as {rows_updated} análises de IA foram redefinidas para 'Não Exportadas'.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"✗ Erro ao redefinir banco de dados: {e}")

if __name__ == "__main__":
    reset_all_exports()
