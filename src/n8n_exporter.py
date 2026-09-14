import os
import sys
import time

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL')

def export_to_n8n():
    if not N8N_WEBHOOK_URL:
        print("Erro: N8N_WEBHOOK_URL não configurado no arquivo .env.")
        print("Por favor, adicione a URL do Webhook do n8n ao .env antes de rodar este script.")
        return

    print("Conectando ao banco de dados Supabase...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Buscar análises que AINDA NÃO foram exportadas
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
                a.algorithm_relevance_score
            FROM public.post_ai_analysis a
            JOIN public.social_posts p ON a.post_id = p.id
            WHERE a.exported_to_zapier = FALSE
        """
        cur.execute(query)
        records = cur.fetchall()

        if not records:
            print("Nenhuma nova análise pendente para exportar para o n8n no momento.")
            return

        print(f"Encontradas {len(records)} análises pendentes. Disparando para o n8n...")

        from datetime import date, datetime
        from decimal import Decimal

        exported_ids = []
        for record in records:
            # Converter tipos não-serializáveis para JSON
            for key, value in record.items():
                if isinstance(value, Decimal):
                    record[key] = float(value)
                elif isinstance(value, (datetime, date)):
                    record[key] = value.isoformat()

            # Enviar para o n8n (POST JSON)
            print(f"Enviando para n8n: {record['content_title'][:50]}...")
            response = requests.post(N8N_WEBHOOK_URL, json=record)
            
            # O n8n costuma retornar status 200, 201 ou "workflow started"
            if response.status_code in [200, 201]:
                print("✓ Sucesso no envio para o n8n!")
                exported_ids.append(record['analysis_id'])
            else:
                print(f"✗ Erro ao enviar para o n8n: {record['content_title'][:30]}: Código {response.status_code} - {response.text}")
            
            # Pequeno delay preventivo para evitar rate limit de destino se houver
            time.sleep(1.5)

        # Marcar como exportado no banco para não enviar duplicado
        if exported_ids:
            update_query = "UPDATE public.post_ai_analysis SET exported_to_zapier = TRUE WHERE id::text = ANY(%s)"
            cur.execute(update_query, (exported_ids,))
            conn.commit()
            print(f"Marcadas {len(exported_ids)} análises como 'Exportadas' no Supabase para evitar duplicação.")

    except Exception as e:
        print(f"Erro na execução do motor de exportação n8n: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    export_to_n8n()
