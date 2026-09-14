import logging
import os
import sys
import traceback

import google.generativeai as genai
import psycopg2
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- Setup ---
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

logger.info(f"Token presente: {bool(TELEGRAM_BOT_TOKEN)}")
logger.info(f"DB presente: {bool(DATABASE_URL)}")
logger.info(f"Gemini Key presente: {bool(GEMINI_API_KEY)}")

genai.configure(api_key=GEMINI_API_KEY)

# Modelos
EMBEDDING_MODEL = "models/gemini-embedding-2"
CHAT_MODEL = genai.GenerativeModel('gemini-2.5-flash')


def get_query_embedding(query):
    """Converte a pergunta do usuário em um vetor matemático."""
    result = genai.embed_content(model=EMBEDDING_MODEL, content=query)
    return result['embedding']


def search_supabase_vector(query_embedding, match_threshold=0.3, match_count=5):
    """Busca vetorial por similaridade no Supabase."""
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM match_post_analysis(%s::vector, %s, %s)",
            (query_embedding, match_threshold, match_count)
        )
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        logger.info(f"Busca vetorial retornou {len(results)} resultados")
        return results
    except Exception as e:
        logger.error(f"Erro na busca vetorial: {e}")
        return []
    finally:
        if conn:
            conn.close()


def search_supabase_fallback():
    """Fallback: busca os últimos 5 dossiês direto do banco, sem vetores."""
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.id, a.post_id, p.content_title,
                a.video_tone, a.editing_style, a.content_summary,
                a.audience_pain_points::text, a.strategic_insights
            FROM public.post_ai_analysis a
            JOIN public.social_posts p ON a.post_id = p.id
            ORDER BY a.analyzed_at DESC
            LIMIT 5
        """)
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        logger.info(f"Fallback retornou {len(results)} resultados")
        return results
    except Exception as e:
        logger.error(f"Erro no fallback: {e}")
        return []
    finally:
        if conn:
            conn.close()


def generate_rag_answer(query, context_records):
    """Gera a resposta usando o Gemini com o contexto do banco de dados."""
    if not context_records:
        return ("🔍 Ainda não encontrei informações suficientes no banco de dados "
                "para responder a essa pergunta específica. "
                "Tente perguntar sobre os vídeos e tendências que já foram coletados!")

    context_text = "DADOS DE TENDÊNCIAS COLETADOS:\n"
    for idx, rec in enumerate(context_records, 1):
        context_text += f"\n--- Dossiê {idx} ---\n"
        context_text += f"Título: {rec.get('content_title', 'N/A')}\n"
        context_text += f"Tom do Criador: {rec.get('video_tone', 'N/A')}\n"
        context_text += f"Estilo de Edição: {rec.get('editing_style', 'N/A')}\n"
        context_text += f"Resumo: {rec.get('content_summary', 'N/A')}\n"
        context_text += f"Dores e Costumes do Público: {rec.get('audience_pain_points', 'N/A')}\n"
        context_text += f"Insights Estratégicos: {rec.get('strategic_insights', 'N/A')}\n"

    prompt = f"""Você é o Oráculo de Inteligência Competitiva, um assistente virtual especializado na 'Creator Economy' e tendências de conteúdo digital.

Seu objetivo é responder à pergunta do usuário baseando-se nos dados contextuais fornecidos abaixo (extraídos de vídeos e comentários reais do YouTube).

Regras:
- Seja direto ao ponto e aja como um estrategista de conteúdo.
- Use tópicos e bullet points para facilitar a leitura.
- Se a resposta não estiver nos dados, diga honestamente que precisa de mais coletas.
- Responda sempre em português brasileiro.

{context_text}

PERGUNTA DO USUÁRIO: {query}

RESPOSTA ESTRATÉGICA:"""

    response = CHAT_MODEL.generate_content(prompt)
    return response.text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start."""
    welcome = (
        "🤖 *Oráculo do Trend Intelligence Engine*\n\n"
        "Eu tenho acesso em tempo real a todos os dossiês de vídeos, "
        "comentários e tendências analisados no nosso sistema.\n\n"
        "💡 Me faça perguntas como:\n"
        "• _Quais são as maiores dores do público sobre a Copa?_\n"
        "• _Que formatos de vídeo estão performando melhor?_\n"
        "• _Resuma as tendências dos criadores de conteúdo._\n\n"
        "Manda a sua pergunta! 👇"
    )
    await update.message.reply_text(welcome, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa as mensagens de texto do usuário (O coração do RAG)."""
    user_query = update.message.text
    logger.info(f">>> Pergunta recebida: {user_query}")

    thinking_msg = await update.message.reply_text(
        "🔍 Consultando a base de inteligência..."
    )

    try:
        # Passo A: Vetorizar a pergunta
        logger.info("Gerando embedding da pergunta...")
        query_vector = get_query_embedding(user_query)
        logger.info(f"Embedding gerado ({len(query_vector)} dims)")

        # Passo B: Busca vetorial
        matches = search_supabase_vector(query_vector)

        # Se não achou por vetor, tenta fallback direto
        if not matches:
            logger.info("Sem matches vetoriais, usando fallback...")
            matches = search_supabase_fallback()

        # Passo C: Gerar resposta com a IA
        logger.info(f"Gerando resposta com {len(matches)} registros de contexto...")
        answer = generate_rag_answer(user_query, matches)

        # Telegram tem limite de 4096 chars por mensagem
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n_(resposta truncada)_"

        await thinking_msg.edit_text(answer)
        logger.info("Resposta enviada com sucesso!")

    except Exception as e:
        error_msg = f"Erro: {type(e).__name__}: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        await thinking_msg.edit_text(
            f"⚠️ Houve um erro ao processar sua pergunta.\n"
            f"Detalhe técnico: `{type(e).__name__}`\n"
            f"Tente novamente em alguns segundos."
        )


if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN não encontrado no .env!")
        sys.exit(1)

    logger.info("🚀 Iniciando o Oráculo RAG no Telegram...")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logger.info("✅ Bot está ONLINE e escutando mensagens!")
    app.run_polling(drop_pending_updates=True)
