# 🏆 Trend Intelligence Engine — Escuta Semântica & Social RAG

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![Contracts](https://img.shields.io/badge/Contracts-Pydantic%20v2-red)](https://docs.pydantic.dev/)
[![LLM](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-magenta.svg)](https://deepmind.google/technologies/gemini/)
[![Embeddings](https://img.shields.io/badge/Embeddings-Gemini%20768d-8A2BE2)](https://ai.google.dev/)
[![Database](https://img.shields.io/badge/Database-Supabase%20pgvector-green.svg)](https://supabase.com/)
[![Work OS](https://img.shields.io/badge/Work%20OS-Monday.com%20GraphQL-00CA72)](https://monday.com/)
[![Orchestrator](https://img.shields.io/badge/Orchestrator-n8n-orange.svg)](https://n8n.io/)
[![Alerts](https://img.shields.io/badge/Bot-Telegram%20Oráculo-2CA5E0?logo=telegram)](https://telegram.org/)

> **[ 🇺🇸 Read in English ](README.md)**

> **Visão Geral Executiva:** O **Trend Intelligence Engine** é uma plataforma especializada de inteligência competitiva, escuta social e análise semântica projetada para extrair sinais de audiência de alta convicção no ecossistema de vídeos digitais. Operando sob o paradigma de **"Dark Kitchen" de Software**, tarefas pesadas de ingestão, otimização de cotas de API, extração de comentários e síntese cognitiva via LLM executam como uma **esteira síncrona em etapas sequenciais** via serviços CLI em Python no *backstage* (com filas assíncronas distribuídas previstas no roadmap arquitetural). A inteligência resultante é entregue diretamente aos tomadores de decisão em painéis no **Monday.com** (com dossiês analíticos completos em HTML), fluxos automatizados no **n8n** e consultas interativas via **Telegram Oráculo** integrado a um banco vetorial com pgvector.

---

## 🎯 1. Valor Comercial & Racional de Engenharia

### A Dor do Mercado: Reação Tardia e Cegueira de Sinal
Diretores de marketing, estrategistas de conteúdo e equipes de mídia esportiva frequentemente reagem tarde a mudanças culturais e comportamentais do público. Ler manualmente milhares de comentários em centenas de vídeos é impraticável, enquanto ferramentas convencionais de monitoramento baseadas em palavras-chave apenas contabilizam volume superficial, perdendo nuances, sarcasmo, gírias emergentes e atritos reais de produto.

### Contraste Narrativa vs. Reação da Audiência
Em vez de simplesmente resumir títulos e descrições, o motor contrasta metodicamente:
* **A Tese do Criador (Narrativa):** O que o influenciador ou canal afirma, defende ou promove na transcrição do vídeo e nos metadados.
* **A Reação Real do Público (Atrito):** O que a audiência efetivamente debate, contesta, questiona ou celebra nas caixas de comentários.

Utilizando o **Gemini 2.5 Flash** com saídas estruturadas em JSON e o **Supabase pgvector (embeddings de 768 dimensões)**, o sistema separa sinais de negócio autênticos do ruído geral das redes.

### Decisões Críticas de Arquitetura
1. **Otimização de Cotas da API do YouTube:** A API v3 do YouTube impõe cota diária padrão de 10.000 unidades. Uma busca (`youtube.search().list`) consome 100 unidades. Requisitar estatísticas individualmente para cada vídeo encontrado consumiria 1 unidade adicional por chamada, esgotando a cota rapidamente. O motor coleta primeiramente os IDs dos candidatos e realiza **requisições em lote de estatísticas** através de `youtube.videos().list(id=','.join(video_ids), part='statistics')` (até 50 IDs por chamada única, consumindo apenas 1 unidade), maximizando a cobertura dentro do limite diário.
2. **Heurística de Dual-Sampling de Comentários:** Injetar centenas de comentários brutos na janela de contexto de um LLM gera custo excessivo de tokens, aumento de latência e dispersão de atenção do modelo. O motor implementa uma estratégia determinística de **Dual-Sampling**:
   * **Top 10 Comentários Mais Curtidos (`top_10`):** Ingeridos integralmente (autor, texto e curtidas) para análise qualitativa profunda, capturando as principais objeções e o sentimento de maior respaldo social.
   * **Amostra de até 100 Comentários (`sample_100`):** Truncados a 150 caracteres cada, fornecendo densidade estatística de sentimento, termos emergentes e dispersão emocional.
   * *Impacto Estimado de Projeto:* Com base na estimativa de contagem de caracteres e tokenização, essa heurística projeta uma economia aproximada de ~65% em tokens comparada ao envio integral de 100 comentários brutos no prompt. Trata-se de uma estimativa de engenharia voltada à redução de custos e foco de atenção do modelo, e não de um benchmark empírico formalizado.
3. **Gestão de Buffer (Lotes Delimitados por Quantidade de Registros):** Ao serializar consultas do banco para o stdout de executores de containers ou nós do n8n, saídas não delimitadas podem estourar os limites de buffer em runtime (como o erro `stdout maxBuffer length exceeded (1MB)` do Node.js). No `src/fetcher.py`, a consulta restringe a quantidade de registros por execução (`WHERE a.exported_to_zapier = FALSE ORDER BY a.id ASC LIMIT 25`) via `RealDictCursor`. Embora o `LIMIT 25` restrinja a contagem de registros e não imponha um teto absoluto em bytes, na prática manteve os payloads observados em cerca de ~300KB nos testes do piloto com dossiês HTML, avançando sequencialmente conforme os registros são exportados e marcados no banco.

---

## 🏗️ 2. Arquitetura do Sistema ("The Dark Kitchen")

A esteira opera de forma modular, desacoplando o enriquecimento de dados da apresentação operacional:

```mermaid
flowchart TD
    Cron["Gatilho Cron / Disparo Manual"] --> Collector["1. Coletor YouTube\n(Busca + Estatísticas em lote até 50 IDs)"]
    Collector --> Scraper["2. Extrator de Comentários\n(Threads ordenadas por relevância)"]
    Scraper --> Analyzer["3. Motor Cognitivo de IA\n(Dual-Sampling + Gemini 2.5 Flash)"]
    Analyzer --> Supabase[("4. Supabase PostgreSQL\n(pgvector 768d + RPC match_post_analysis)")]
    Supabase --> Fetcher["5. Fetcher em Lotes\n(LIMIT 25 delimitado em pendentes)"]
    Fetcher --> Distribution{"Canais de Distribuição"}
    Distribution --> Monday["Monday.com Work OS\n(Itens GraphQL + Dossiês HTML em updates)"]
    Distribution --> N8N["Despachante n8n\n(Orquestração e webhooks)"]
    Supabase <--> Telegram["Bot Telegram Oráculo\n(Busca vetorial + Fallback relacional)"]
```

### 📡 Camadas do Pipeline

* **Camada de Ingestão (`src/collector.py`):** Consultas orientadas a arquivo de configuração via YouTube API v3. Filtra vídeos por engajamento e visualizações em relação ao tempo de publicação, utilizando buscas de IDs seguidas de chamadas em lote de estatísticas (até 50 vídeos por unidade de cota).
* **Extração de Comentários (`src/scraper.py`):** Capta comentários ordenados por relevância via `youtube.commentThreads().list`, gravando autor, texto, contagem de curtidas e data de publicação com deduplicação no banco relacional.
* **Motor Cognitivo (`src/analyzer.py`):** Combina metadados do vídeo, transcrição do áudio (via `youtube-transcript-api`) e o **corpus em Dual-Sampling** (10 completos + até 100 truncados). Gera saída estritamente estruturada em JSON com o Gemini 2.5 Flash e calcula embeddings vetoriais de 768 dimensões com `models/gemini-embedding-2` gravados no Supabase PostgreSQL.
* **Fetcher em Lotes & Formatador de Payloads (`src/fetcher.py`):** Consulta análises não exportadas em lotes de até 25 registros (`WHERE exported_to_zapier = FALSE ORDER BY id ASC LIMIT 25`) via `RealDictCursor`. Embora limite a quantidade de registros e não garanta um teto rígido em bytes, reduz substancialmente o risco de estouro de buffer no stdout dos executores. Resolve dinamicamente os IDs de grupos no Monday, mapeia status de sentimento, separa seções de narrativa vs. reação e monta dossiês analíticos completos em HTML.
* **Integração Work OS (`src/export_to_monday.py`):** Realiza mutações GraphQL para o Monday.com, criando itens nos grupos correspondentes aos sub-temas e publicando o dossiê detalhado em HTML nos balões de atualização do item.
* **Oráculo Interativo (`src/telegram_oraculo.py`):** Bot no Telegram permitindo consultas em linguagem natural. Converte as perguntas em vetores de 768d e executa busca por similaridade de cosseno via função SQL `match_post_analysis(%s::vector, %s, %s)`, contando com fallback relacional para as últimas 5 análises caso a busca vetorial não retorne correspondências.

---

## ⚽ 3. Piloto de Inteligência de Conteúdo: Copa do Mundo 2026

Como prova de conceito em um cenário de alto volume e relevância na mídia esportiva, o motor foi configurado para o ecossistema da **Copa do Mundo FIFA 2026**:

* **Escopo e Volume Observado no Piloto:** Em execuções de teste reportadas durante a estruturação do piloto, 163 vídeos foram indexados e analisados ao longo dos 5 sub-tópicos configurados, demonstrando que os esquemas, o mapeamento de sentimento e os despachos para o Monday.com operam de ponta a ponta sem intervenção manual.
* **Categorização Dinâmica de Sub-temas:**
  * `figurinhas`: Engajamento em torno do álbum Panini, itens colecionáveis e sensibilidade a preços.
  * `tatica`: Análises táticas pós-jogo, avaliações de escalações e comentários esportivos.
  * `duvidas`: Especulações de convocação, debates sobre atletas em boa/má fase e repercussão de listas.
  * `polemicas`: Custos de ingressos, logística da FIFA e atritos operacionais do evento.
  * `influencers`: Conteúdo de criadores em ascensão, reacts e dinâmica de retenção de público.
* **Mapeamento Automático de Grupos:** O motor mapeia dinamicamente cada vídeo para seu grupo correspondente no Monday.com (`Figurinhas da Copa 2026`, `Tática e React de Jogos`, etc.), mantendo a esteira editorial organizada sem intervenção humana.
* **Isolamento de Configuração:** Todas as palavras-chave, parâmetros de corte e ângulos analíticos estão centralizados em `src/pilots/world_cup_2026/config.yaml`.

> [!NOTE]
> **Contexto de Uso:** Este piloto foi construído como demonstração técnica independente de engenharia de software e inteligência de mídia. Não implica nem afirma qualquer vínculo comercial oficial, patrocínio ou contrato com LiveMode, CazéTV, FIFA ou Panini.

---

## 🛡️ 4. Contratos de Dados & Resiliência Arquitetural

### Contratos de Dados & Esquemas (Pydantic v2)
Os contratos de dados são formalmente declarados com modelos Pydantic v2 em `src/models/schemas.py` (`VideoMetadata`, `CommentPayload`, `SentimentAnalysisResult` e `MondayItemPayload`), definindo os esquemas tipados esperados entre as camadas de coleta, análise e distribuição. Na execução atual do pipeline, o fluxo interno trafega predominantemente como dicionários estruturados em Python, com a imposição estrita de validação em runtime sendo expandida progressivamente entre todas as etapas.

### RAG Defensivo com Fallback Relacional
No `src/telegram_oraculo.py`, as consultas ao repositório utilizam similaridade de cosseno com pgvector:
```sql
SELECT * FROM match_post_analysis(query_embedding::vector, match_threshold, match_count);
```
Caso a busca vetorial não encontre resultados satisfatórios ou ocorra indisponibilidade no índice vetorial, o sistema degrada graciosamente para uma busca relacional, retornando os 5 dossiês mais recentes ordenados por data de análise.

---

## 🔍 5. Status de Engenharia & Alinhamento de CI

Para garantir absoluta transparência técnica sobre o baseline do repositório:

* **Branch Pública `main` (Baseline):** Contém a arquitetura fundamental da esteira, batching de API do YouTube, motor cognitivo com Dual-Sampling, esquema de banco no Supabase, exportadores GraphQL para Monday.com e configuração do piloto da Copa 2026. Ressalta-se que o workflow de CI padrão na `main` atualmente falha devido a uma importação legada de modelo (`ImportError: AnalysisResult` em `tests/conftest.py`).
* **Melhorias de Engenharia em Homologação (Commits Locais & Backup Privado):** A correção das importações de modelos, o aprimoramento da configuração de ambiente e a suíte completa de **29 testes unitários determinísticos** (cobrindo contratos de dados, funções de extração e mapeamentos para Monday.com) estão atualmente preservadas em commits locais de homologação (e espelhadas em backup privado). Essas melhorias estão organizadas para revisão e integração em ciclo planejado de release, mantendo um histórico auditável e controlado.

---

## 🚀 6. Como Executar Localmente

### Pré-requisitos
* Python 3.11+
* Docker & Docker Compose (opcional, para instâncias locais do n8n)
* Chaves de API configuradas:
  * YouTube Data API v3 (`YOUTUBE_API_KEY`)
  * Google Gemini API (`GEMINI_API_KEY`)
  * String de conexão PostgreSQL do Supabase (`DATABASE_URL`)
  * Token da API Monday.com (`MONDAY_API_TOKEN`)
  * Token de Bot do Telegram (`TELEGRAM_BOT_TOKEN`, opcional para o Oráculo)

### Instalação
```bash
# 1. Clonar o repositório
git clone https://github.com/jraphaelcunha/trend-intelligence-engine.git
cd trend-intelligence-engine

# 2. Configurar o ambiente virtual
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Preencher .env com suas chaves reais
```

### Execução dos Módulos
```bash
# Executar coleta no YouTube para o piloto configurado
python src/collector.py

# Extrair comentários dos vídeos indexados
python src/scraper.py

# Executar enriquecimento cognitivo com Gemini 2.5 Flash
python src/analyzer.py

# Exportar dossiês pendentes para o Monday.com
python src/export_to_monday.py

# Inicializar o bot interativo do Telegram Oráculo
python src/telegram_oraculo.py
```

### Executando com Docker Compose
```bash
docker compose -f docker/docker-compose.yml up --build -d
```
A interface do n8n estará acessível em [http://localhost:5678](http://localhost:5678).

---

## 📂 7. Estrutura Canônica do Repositório

```text
trend-intelligence-engine/
├── .github/
│   └── workflows/
│       ├── ci.yml                     # Automação de lint e testes no GitHub Actions
│       └── google-cloudrun.yml        # Workflow de deploy no Google Cloud Run
├── docker/                            # Arquivos Dockerfile multi-stage e Compose
├── n8n/                               # Exportações dos fluxos do n8n
├── src/                               # Código-fonte principal em Python
│   ├── models/
│   │   └── schemas.py                 # Contratos de dados em Pydantic v2
│   ├── collector.py                   # Ingestão do YouTube com estatísticas em lote
│   ├── scraper.py                     # Extração de comentários e deduplicação
│   ├── analyzer.py                    # Motor cognitivo Gemini 2.5 Flash e embeddings 768d
│   ├── fetcher.py                     # Fetcher delimitado de 25 registros e formatador Monday
│   ├── export_to_monday.py            # Exportador direto para GraphQL da Monday.com
│   ├── telegram_oraculo.py            # Assistente RAG conversacional com fallback relacional
│   ├── utils/
│   │   └── db.py                      # Gerenciamento de conexão com Supabase PostgreSQL
│   └── pilots/
│       └── world_cup_2026/            # Configuração e taxonomia de sub-temas do piloto
├── scripts/
│   └── ops/                           # Utilitários de manutenção operacional e de banco
├── tests/
│   ├── conftest.py                    # Fixtures globais e mocks de API para Pytest
│   └── unit/
│       ├── test_schemas.py            # Testes de validação dos contratos Pydantic
│       ├── test_fetcher.py            # Testes de mapeamento e transformação
│       └── test_analyzer.py           # Testes heurísticos e de extração de IDs
├── requirements.txt                   # Dependências de produção
├── README.md                          # Documentação técnica em inglês
└── README.pt-br.md                    # Documentação técnica em português
```

---

## 🗺️ 8. Próximos Passos (Roadmap)

- [ ] **Ingestão Multiplataforma:** Expandir a coleta além do YouTube para transcrições de vídeos curtos no TikTok e Instagram Reels.
- [ ] **Roteamento Multi-Board no Monday:** Suporte dinâmico a múltiplos boards corporativos via cabeçalhos e tokens nas requisições do n8n.
- [ ] **Alertas Ativos de Tendência:** Disparo de notificações proativas no Telegram quando um sub-tema apresentar picos anômalos de atrito ou engajamento.
- [ ] **Filas de Tarefas Assíncronas:** Evoluir os scripts CLI síncronos em etapas para workers assíncronos com filas distribuídas (ex.: Celery/Redis ou loop de tarefas em asyncio) para ingestão paralela de alta concorrência.

---

## 👤 Autor

**João Raphael Cunha**<br/>
Solutions Architect & AI Engineer<br/>
[Perfil no GitHub](https://github.com/jraphaelcunha) | [LinkedIn](https://www.linkedin.com/in/joaoraphaelcunha/)
