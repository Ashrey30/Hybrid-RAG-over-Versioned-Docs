# Hybrid RAG over Versioned Documents

A document-grounded question-answering prototype that combines keyword and vector search, version-aware indexing, citations, and adaptive retrieval. The demonstration corpus is Kubernetes documentation; the ingestion pipeline is designed to work with configured Markdown collections, including unversioned documents.

> **Project status:** Research and portfolio prototype, not a production-ready hosted service. Evaluation is limited to a small Kubernetes question set. Do not index confidential documents without reviewing the access labels, provider data handling, and deployment security.

[![CI](https://github.com/Ashrey30/Hybrid-RAG-over-Versioned-Docs/actions/workflows/ci.yml/badge.svg)](https://github.com/Ashrey30/Hybrid-RAG-over-Versioned-Docs/actions/workflows/ci.yml)

## What it does

- Retrieves evidence with hybrid BM25 keyword and dense-vector search.
- Produces answers with citations and is prompted to abstain when document evidence is insufficient.
- Indexes versioned or unversioned Markdown sources. The demo uses Kubernetes documentation releases v1.30 and v1.31; normal app queries prefer the latest indexed content.
- Uses an adaptive router to choose retrieval depth (`k ∈ {0, 2, 5, 10}`).
- Supports user and administrator roles, with document access filters applied by the API.
- Provides exact and semantic response caching, an injection-classifier check, and admin request metrics.
- Includes a browser-based chat interface with citations, suggested questions, and session history stored in the browser until sign-out.

This repository does not include the source corpus, generated chunks, vector database, account database, LLM cache, or raw per-question evaluation outputs. The configured ingestion process fetches the public Kubernetes documentation when you build the index.

## Architecture

```text
Markdown sources
    -> version-aware parsing and chunking
    -> deduplication and embeddings
    -> Qdrant (dense vectors + BM25)

User question
    -> prompt-injection check / capability fast path
    -> embedding and cache lookup
    -> adaptive retrieval router
    -> access-filtered hybrid search
    -> answer generation and citation validation
    -> cited response
```

| Area | Current implementation |
|---|---|
| API | FastAPI / Python 3.11 |
| Vector database | Qdrant |
| Dense embeddings | `BAAI/bge-small-en-v1.5` (384 dimensions) |
| Keyword retrieval | BM25 with reciprocal-rank fusion |
| Answer generation | Groq API using `qwen/qwen3.8-27b` by default |
| Injection check | Llama Prompt Guard 2, local inference |
| Frontend | Static HTML, CSS, and JavaScript |
| Local deployment | Docker Compose |

## Evaluation snapshot

On the current 89-question development set, the full system with router v2 scored **74/89 correct (83.1%)**. These results are not an independent held-out estimate: the set is small, and a label was corrected after reviewing evidence. The result should not be interpreted as a general accuracy guarantee.

| Configuration | Correct answers | Correct abstention | False abstention | Citation hit |
|---|---:|---:|---:|---:|
| Dense baseline | 61/89 (68.5%) | 9/9 (100%) | 25.0% | 55/60 (91.7%) |
| Hybrid, fixed k=5 | 63/89 (70.8%) | 7/9 (77.8%) | 23.8% | 56/60 (93.3%) |
| Adaptive router v2 | **74/89 (83.1%)** | 7/9 (77.8%) | **10.0%** | 56/60 (93.3%) |

Latency was measured sequentially, not under concurrent load. In the 89-question warm/mixed run, total latency was 254 ms p50 and 3.05 s p95 with 66/89 cache hits. The cold run had 713 ms p50 and 60.9 s p95. Dollar operating cost has not been measured.

**Semantic caching is experimental.** The configured verifier reduced but did not eliminate incorrect near-miss cache hits: a fresh 45-pair test recorded 15.6% false serves at the configured thresholds. For correctness-sensitive use, disable semantic caching in `config.yaml` until it passes a larger independent safety evaluation. Exact caching is a separate tier, but can still repeat an initially incorrect answer.

See the [stakeholder report](PROJECT_FINAL_REPORT.md) for evaluation definitions and caveats, latency and cost, security limits, scaling evidence, failure modes, and the roadmap. Supporting summaries are in [`results/`](results/).

## Document access and privacy

- New self-registered accounts receive the `user` role. Admin accounts must be provisioned separately.
- User accounts retrieve public documents. Admin accounts can retrieve public and restricted documents and view request metrics.
- A Markdown source can set `access_group: restricted` in YAML front matter to mark its chunks as restricted. Documents without this field currently default to public.
- The current demo index contains public Kubernetes documentation only. Restricted-document access must be tested with an explicitly restricted source before relying on it.
- The current ingestion path supports configured Markdown sources; it does not offer user uploads, PDF/DOCX parsing, cloud-drive connectors, or URL ingestion.
- On cache misses, the question and retrieved context are sent to the configured Groq model. Review the provider's data-handling terms before sending private or regulated content.
- Chat history is browser-local and is not synchronized across devices.

Never commit `.env`, API keys, account databases, local document collections, generated indexes, or raw evaluation data. The repository ignore rules exclude these local files; review `git status --ignored` before publishing changes.

## Quick start (Windows PowerShell)

### Prerequisites

- Python 3.11
- Git
- Docker Desktop with Docker Compose
- A Groq API key for answer generation

### 1. Get the code and install Python dependencies

```powershell
git clone https://github.com/Ashrey30/Hybrid-RAG-over-Versioned-Docs.git
cd Hybrid-RAG-over-Versioned-Docs
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `.env` and set `GROQ_API_KEY`. Keep the real key in this ignored local file; never paste it into source code or commit it. The optional `GEMINI_API_KEY` is only needed if the provider configuration is changed to Gemini.

### 2. Start Qdrant and build the document index

```powershell
docker compose up -d qdrant
python -m ingest.index
```

The ingestion command clones the configured Kubernetes documentation branches into the ignored `data/raw` directory, writes chunks and manifests under `data`, then recreates and fills the configured Qdrant collection. Re-running it rebuilds that collection; do not point it at a collection containing data you need to preserve.

To index another Markdown corpus, update the `corpus` section of `config.yaml`. For unversioned local Markdown, configure the local source path and omit version entries. Review `access_group` labels before indexing any non-public documents.

### 3. Create an administrator and start the app

```powershell
python -m api.bootstrap_admin
docker compose up --build -d api
```

The admin setup command prompts for an email and password and stores only a salted password hash in the local ignored SQLite database. Ordinary users can register from the sign-in page.

Open [http://localhost:8000](http://localhost:8000). Check [http://localhost:8000/health](http://localhost:8000/health) for the API health response.

Useful local commands:

```powershell
docker compose logs -f api
docker compose down
python -m pytest -q
ruff check .
```

For HTTPS deployments, set `AUTH_COOKIE_SECURE=true`. Do not expose this development configuration directly to the public internet.

## Repository layout

| Path | Contents |
|---|---|
| `api/` | FastAPI app, authentication, and static web UI |
| `common/` | Configuration, embeddings, LLM client, and shared utilities |
| `ingest/` | Markdown source loading, chunking, deduplication, and indexing |
| `retrieve/` | Adaptive retrieval router and search |
| `generate/` | Answer and citation generation |
| `guard/` | Access filtering, prompt-injection check, and cache matching |
| `eval/` | Evaluation runners |
| `tests/` | Unit and API tests |
| `results/*.md` | Curated aggregate evaluation summaries (not raw run data) |
| `PROJECT_FINAL_REPORT.md` | Stakeholder-oriented project report |

## Known limitations

- Quality has only been measured on the small Kubernetes development corpus; other domains and source types need independent evaluation.
- Semantic-cache false positives remain unresolved; the semantic tier is enabled in the current config but should be treated as experimental.
- The cold-run p95 is high because generation can be slow. No concurrent capacity, reliability, or recovery test has been completed.
- Actual provider billing and per-request dollar cost are not measured.
- The current access test predates the explicit document-level restricted-label model; repeat it with restricted test content.
- There is no multi-tenant isolation, managed document ingestion, server-side chat history, or production operations setup.

## Contributing and validation

The GitHub Actions workflow runs Ruff and the test suite on pushes and pull requests:

```powershell
ruff check .
python -m pytest -q
```

Evaluation commands may call hosted models and create local output data. They can incur provider usage and are intentionally not part of the default CI run.
