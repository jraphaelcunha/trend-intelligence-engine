import os
import time

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

def get_connection(retries=3, delay=2):
    """
    Retorna uma conexão estável com o Supabase PostgreSQL.
    Implementa um mecanismo básico de retry para resiliência.
    """
    if not DATABASE_URL:
        raise ValueError("CRITICAL: A variável de ambiente DATABASE_URL não está configurada.")
        
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except psycopg2.OperationalError as e:
            if attempt == retries:
                print(f"❌ Erro crítico ao conectar ao Supabase na tentativa {attempt}/{retries}: {e}")
                raise e
            print(f"⚠️ Falha de conexão na tentativa {attempt}/{retries}. Tentando novamente em {delay}s...")
            time.sleep(delay)

def execute_query(query, params=None, fetch=False):
    """
    Executa uma query de forma segura, garantindo o fechamento dos cursores e conexões.
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
    finally:
        conn.close()
