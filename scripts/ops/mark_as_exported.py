import os
import sys
import argparse
import psycopg2
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def main():
    parser = argparse.ArgumentParser(description="Marca uma análise de IA específica como exportada no Supabase.")
    parser.add_argument("--id", required=True, help="ID da análise a ser marcada como exportada.")
    args = parser.parse_args()

    if not DATABASE_URL:
        print("Erro: DATABASE_URL não configurado no .env")
        sys.exit(1)

    print(f"Marcando análise {args.id} como exportada no banco de dados Supabase...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        query = "UPDATE public.post_ai_analysis SET exported_to_zapier = TRUE WHERE id::text = %s"
        cur.execute(query, (args.id,))
        conn.commit()

        print(f"✓ Sucesso! Análise {args.id} marcada como exportada no Supabase.")
    except Exception as e:
        print(f"✗ Erro ao atualizar banco: {e}")
        sys.exit(1)
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    main()
