# 🏆 Trend Intelligence Engine — Semantic Listening & Social RAG

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![Contracts](https://img.shields.io/badge/Contracts-Pydantic%20v2-red)](https://docs.pydantic.dev/)
[![LLM](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-magenta.svg)](https://deepmind.google/technologies/gemini/)
[![Embeddings](https://img.shields.io/badge/Embeddings-Gemini%20768d-8A2BE2)](https://ai.google.dev/)
[![Database](https://img.shields.io/badge/Database-Supabase%20pgvector-green.svg)](https://supabase.com/)
[![Work OS](https://img.shields.io/badge/Work%20OS-Monday.com%20GraphQL-00CA72)](https://monday.com/)
[![Orchestrator](https://img.shields.io/badge/Orchestrator-n8n-orange.svg)](https://n8n.io/)
[![Alerts](https://img.shields.io/badge/Bot-Telegram%20Oráculo-2CA5E0?logo=telegram)](https://telegram.org/)

> **[ 🇧🇷 Ler em Português ](README.pt-br.md)**

> **Executive Overview:** The **Trend Intelligence Engine** is a professional social listening, market intelligence, and semantic analysis platform developed starting in early 2026. Designed to extract high-conviction audience signals, emerging sentiment shifts, and commercial objections from digital video ecosystems, the system operates on a **Software "Dark Kitchen"** architecture: heavy data ingestion, quota-optimized API batching, comment mining, and LLM-driven cognitive synthesis run as a **synchronous, staged execution pipeline** in Python CLI services in the backstage (with asynchronous distributed queues on the architectural roadmap). Enriched intelligence is delivered directly to decision-makers via enterprise Work OS boards (**Monday.com** with rich HTML update dossiers), workflow automations (**n8n** webhooks), and interactive conversational search (**Telegram Oráculo** with pgvector RAG).

---

## 🎯 1. Commercial Value & Engineering Rationale

### The Problem: Late Reaction and Signal Blindness
Marketing directors, content strategists, and brand leaders frequently react late to cultural shifts and audience sentiment changes. Manually reading thousands of comments across hundreds of videos is impossible, while traditional keyword scrapers only count surface volumes, missing sarcasm, emergent community slang, and qualitative product friction.

### Narrative vs. Audience Reaction Contrast
Rather than merely summarizing video titles or descriptions, the engine systematically contrasts:
* **The Creator's Thesis (The Narrative):** What the creator claims, defends, or promotes in the video transcription and metadata.
* **The Audience's Real Reaction (The Friction):** What viewers actively debate, reject, question, or celebrate across comment threads, exposing authentic market objections and consumer sentiment.

Using **Gemini 2.5 Flash** with structured JSON output and **Supabase pgvector (768-dimensional embeddings)**, the engine isolates actionable business signals from background noise.

### Key Architectural Decisions
1. **YouTube API Quota Batching:** The YouTube Data API v3 enforces a default daily quota limit of 10,000 units. A standard search request (`youtube.search().list`) consumes 100 units. Requesting statistics individually for each returned video would consume 1 unit per call and quickly exhaust quotas. The engine gathers candidate video IDs first, then performs **batched statistics requests** via `youtube.videos().list(id=','.join(video_ids), part='statistics')` (up to 50 video IDs per single API call consuming only 1 unit), enabling high-coverage discovery within strict API constraints.
2. **Dual-Sampling Comment Heuristic:** Passing hundreds of complete comments into an LLM context window causes unnecessary token inflation, latency, and context dispersion. The engine implements a deterministic **Dual-Sampling** strategy:
   * **Top 10 Most-Liked Comments (`top_10`):** Ingested in full (author, text, likes) to capture high-conviction qualitative critique, major counterarguments, and top community sentiment.
   * **Sample of Up to 100 Comments (`sample_100`):** Truncated to 150 characters each to provide broad sentiment density, keyword emergence, and emotional tone.
   * *Estimated Design Impact:* Based on prompt length and tokenization estimates, this heuristic targets approximately ~65% token savings compared to passing 100 full raw comments into the prompt context. This is an architectural design estimate aimed at cost reduction and attention focus rather than a formal empirical benchmark across arbitrary corpora.
3. **Buffer Management (Bounded Record Batching):** When serializing database queries to stdout for container runners or n8n nodes, unbounded query outputs risk triggering runtime buffer exceptions (such as Node.js's `stdout maxBuffer length exceeded (1MB)`). In `src/fetcher.py`, the query limits results by record count (`WHERE a.exported_to_zapier = FALSE ORDER BY a.id ASC LIMIT 25`) using `RealDictCursor`. While `LIMIT 25` bounds the quantity of records rather than imposing an absolute byte ceiling, in practice with typical metadata and HTML update dossiers it kept observed payload sizes around ~300KB in reported test runs, advancing sequentially as records are exported and marked in the database.

---

## 🏗️ 2. System Architecture ("The Dark Kitchen")

The pipeline separates data intelligence from operational presentation:

```mermaid
flowchart TD
    Cron["Cron Trigger / Manual Dispatch"] --> Collector["1. YouTube Collector\n(Search + Batched stats up to 50 IDs)"]
    Collector --> Scraper["2. Comment Scraper\n(Relevance-sorted threads)"]
    Scraper --> Analyzer["3. AI Cognitive Engine\n(Dual-Sampling + Gemini 2.5 Flash)"]
    Analyzer --> Supabase[("4. Supabase PostgreSQL\n(pgvector 768d + match_post_analysis RPC)")]
    Supabase --> Fetcher["5. Batch Fetcher\n(Bounded LIMIT 25 on unexported records)"]
    Fetcher --> Distribution{"Distribution Channels"}
    Distribution --> Monday["Monday.com Work OS\n(GraphQL items + HTML update dossiers)"]
    Distribution --> N8N["n8n Webhook Dispatcher\n(Automated workflow orchestration)"]
    Supabase <--> Telegram["Telegram Oráculo Bot\n(Vector similarity search + Relational fallback)"]
```

### 📡 Pipeline Layers

* **Ingestion Layer (`src/collector.py`):** Config-driven keyword and subtopic queries via YouTube API v3. Uses candidate ID collection followed by batched statistics requests (up to 50 IDs/call) and filters candidates by minimum view counts and engagement ratios over elapsed time.
* **Comment Extraction (`src/scraper.py`):** Captures relevance-ordered comment threads via `youtube.commentThreads().list`, extracting author names, text, like counts, and publication timestamps with automatic deduplication in `post_comments`.
* **Cognitive Engine (`src/analyzer.py`):** Combines video metadata, video transcription (via `youtube-transcript-api`), and the **Dual-Sampling comment corpus** (Top 10 full + up to 100 truncated). Generates structured JSON via Gemini 2.5 Flash and produces 768-dimensional vector embeddings using `models/gemini-embedding-2` persisted into Supabase PostgreSQL.
* **Batch Fetcher & Payload Formatter (`src/fetcher.py`):** Queries unexported analyses in batches of up to 25 records (`WHERE exported_to_zapier = FALSE ORDER BY id ASC LIMIT 25`) using `RealDictCursor`. While this limits the record count rather than enforcing a strict byte cap, it substantially mitigates stdout buffer overflow risks in execution runners. It resolves Monday group IDs dynamically, maps sentiment tags, extracts narrative vs. reaction sections, and formats rich HTML briefing dossiers for export.
* **Work OS Integration (`src/export_to_monday.py`):** Issues typed GraphQL mutations to Monday.com, creating items under dynamic subtopic groups and posting detailed HTML briefing dossiers directly into item update bubbles.
* **Interactive Oráculo (`src/telegram_oraculo.py`):** Telegram bot allowing stakeholders to query indexed dossiers using natural language. Converts queries to 768d embeddings and executes PostgreSQL vector similarity search via `match_post_analysis(%s::vector, %s, %s)`, with automatic relational fallback to recent analyses if vector search yields no results.

---

## ⚽ 3. Domain Configuration: 2026 FIFA World Cup

While the Trend Intelligence Engine is architected as a general-purpose social listening framework, a dedicated domain configuration was deployed in early 2026 focusing on the **2026 FIFA World Cup** ecosystem to evaluate multi-subtopic classification and high-volume audience reception:

* **Reported Execution Volume:** Project execution logs report **163 indexed videos** and an estimated volume of **over 150,000 comments** processed across the configured subtopics. These figures represent reported operational metrics from project runs and testing logs, to be validated against database execution records, rather than independently certified production benchmarks.
* **Dynamic Subtopic Categorization:**
  * `figurinhas`: Panini sticker album hype, collectible trading trends, and pricing sentiment.
  * `tatica`: Tactical analysis, post-match reviews, and formation debates.
  * `duvidas`: Squad speculation, national team call-up debates, and player form controversies.
  * `polemicas`: Ticketing costs, FIFA organizational logistics, and fan travel concerns.
  * `influencers`: Rising creators, react formats, and creator economy engagement.
* **Automated Group Mapping:** The engine dynamically resolves subtopics to designated Monday.com groups (`Figurinhas da Copa 2026`, `Tática e React de Jogos`, etc.), keeping content editorial boards structured without manual triaging.
* **Decoupled Configuration:** All search queries, minimum engagement thresholds, and analysis angles are isolated in `src/pilots/world_cup_2026/config.yaml`, allowing seamless swapping to other corporate or market intelligence domains.

---

## 🛡️ 4. Data Contracts & Architecture Resilience

### Data Contracts & Schemas (Pydantic v2)
Typed data schemas are formally declared using Pydantic v2 in `src/models/schemas.py` (`VideoMetadata`, `CommentPayload`, `SentimentAnalysisResult`, and `MondayItemPayload`), specifying the expected interface contracts between collection, analysis, and distribution layers. In the current runtime pipeline, intermediate data flows primarily as Python dictionaries, with full end-to-end runtime model validation actively being extended across all pipeline stages.

### Defensive RAG with Relational Fallback
In `src/telegram_oraculo.py`, queries against the knowledge base use cosine similarity over pgvector embeddings:
```sql
SELECT * FROM match_post_analysis(query_embedding::vector, match_threshold, match_count);
```
If vector matching returns empty results or encounters connection timeouts, the system gracefully degrades to a relational fallback, retrieving the 5 most recent complete dossiers ordered by analysis timestamp.

---

## 🔍 5. Engineering Status & CI Alignment

To maintain absolute technical transparency regarding the repository baseline:

* **Public `main` Branch (Baseline):** Contains the foundational pipeline architecture, YouTube quota batching, Dual-Sampling cognitive engine, Supabase database schema, Monday.com GraphQL integration, and the 2026 World Cup domain configuration.
* **Staged Engineering Improvements (Local & Private Backup):** Model import alignment, environment configuration hardening, and test suite stabilization are currently maintained in local staging commits (and mirrored in private backup). These updates are queued for review and integration in an upcoming release cycle, preserving a disciplined verification history.

---

## 🚀 6. Local Setup & Quickstart

### Prerequisites
* Python 3.11+
* Docker & Docker Compose (optional, for local n8n instance)
* API Credentials:
  * YouTube Data API v3 (`YOUTUBE_API_KEY`)
  * Google Gemini API (`GEMINI_API_KEY`)
  * Supabase PostgreSQL connection string (`DATABASE_URL`)
  * Monday.com API Token (`MONDAY_API_TOKEN`)
  * Telegram Bot Token (`TELEGRAM_BOT_TOKEN`, optional for Oráculo)

### Installation
```bash
# 1. Clone repository
git clone https://github.com/jraphaelcunha/trend-intelligence-engine.git
cd trend-intelligence-engine

# 2. Configure virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your credentials
```

### Running the Pipeline Components
```bash
# Run YouTube collector for active domain configuration
python src/collector.py

# Extract comments for indexed videos
python src/scraper.py

# Run cognitive analysis with Gemini 2.5 Flash
python src/analyzer.py

# Export pending dossiers to Monday.com
python src/export_to_monday.py

# Start interactive Telegram Oráculo bot
python src/telegram_oraculo.py
```

### Running with Docker Compose
```bash
docker compose -f docker/docker-compose.yml up --build -d
```
The n8n orchestrator console will be available at [http://localhost:5678](http://localhost:5678).

---

## 📂 7. Repository Structure

```text
trend-intelligence-engine/
├── .github/
│   └── workflows/
│       ├── ci.yml                     # Automated Lint & Pytest Quality Gate
│       └── google-cloudrun.yml        # Google Cloud Run deployment workflow
├── docker/                            # Multi-stage Dockerfile & Compose definitions
├── n8n/                               # Exported n8n orchestration workflows
├── src/                               # Core Python source code
│   ├── models/
│   │   └── schemas.py                 # Pydantic v2 data contracts
│   ├── collector.py                   # YouTube API ingestion with batched stats
│   ├── scraper.py                     # Comment extraction & deduplication
│   ├── analyzer.py                    # Gemini 2.5 Flash cognitive engine & 768d embeddings
│   ├── fetcher.py                     # Bounded 25-record batch fetcher & Monday payload formatter
│   ├── export_to_monday.py            # Direct Monday.com GraphQL exporter
│   ├── telegram_oraculo.py            # Conversational RAG assistant with relational fallback
│   ├── utils/
│   │   └── db.py                      # Supabase PostgreSQL connection pooling
│   └── pilots/
│       └── world_cup_2026/            # Domain configuration & subtopic taxonomy
├── scripts/
│   └── ops/                           # Operational and database maintenance utilities
├── tests/
│   ├── conftest.py                    # Pytest fixtures and API mocks
│   └── unit/
│       ├── test_schemas.py            # Pydantic contract validation tests
│       ├── test_fetcher.py            # Transformation & mapping unit tests
│       └── test_analyzer.py           # ID extraction & heuristic tests
├── requirements.txt                   # Production dependencies
├── README.md                          # English technical documentation
└── README.pt-br.md                    # Portuguese technical documentation
```

---

## 🗺️ 8. Roadmap

- [ ] **Multi-Platform Ingestion:** Extend collection pipeline beyond YouTube to TikTok and Instagram Reels video transcripts.
- [ ] **Multi-Tenant Board Routing:** Support dynamic routing across multiple Monday.com boards via webhook headers in n8n.
- [ ] **Proactive Trend Alerts:** Scheduled push notifications in Telegram when a subtopic exhibits anomalous negative friction or sudden engagement spikes.
- [ ] **Asynchronous Task Queue:** Transition sequential batch CLI scripts to asynchronous worker queues (e.g., Celery/Redis or asyncio task loops) for high-concurrency ingestion.

---

## 👤 Author

**João Raphael Cunha**<br/>
Solutions Architect & AI Engineer<br/>
[GitHub Profile](https://github.com/jraphaelcunha) | [LinkedIn](https://www.linkedin.com/in/joaoraphaelcunha/)
