# Healthcare Knowledge Navigator — Backend (v0, base build)

Real, running FastAPI backend implementing the architecture from the
project roadmap. This replaces the single-file HTML prototype with an
actual service you can deploy, extend, and swap providers on.

## What's real vs. stubbed right now

| Component | Status |
|---|---|
| Chunking (structure-aware, section-tagged) | **Real** |
| BM25 sparse retrieval | **Real** |
| Vector store (Qdrant, in-memory or server mode) | **Real** |
| Hybrid fusion (RRF) + source-diversity filter | **Real** |
| Reranking | **Lexical-overlap proxy** — swap `CrossEncoderReranker` for a real cross-encoder (BAAI/bge-reranker-large or Cohere Rerank) when you have network access to that model/API |
| Embeddings | **Deterministic hash stub** (`local_stub`) for offline dev — swap to `openai` or `voyage` in `.env` for real semantic retrieval. Code for both is already written in `app/retrieval/embeddings.py`, just needs a real API key + network path |
| Generation (Claude, grounded synthesis + structured citations) | **Real** — calls the actual Anthropic API |
| Faithfulness checking | **Lexical-overlap proxy** — swap for a real NLI model in `app/generation/faithfulness.py` |
| Confidence scoring (composite, weighted, transparent breakdown) | **Real** |
| Postgres audit log + feedback storage | **Real** (schema + endpoints wired; needs `docker-compose up postgres` or a real DSN) |
| Auth (JWT/OIDC) | **Not yet implemented** — config placeholders exist, endpoints are currently open |

This mirrors how the roadmap said to sequence it: get the real architecture running end-to-end with the cheapest possible stand-ins for the two things that need external network/paid access (embeddings, reranking), then swap those in without touching anything else.

## Project layout

```
hkn/
  backend/
    app/
      core/        # config, DI wiring
      models/      # pydantic schemas (single source of truth for all layers)
      ingestion/    # chunking, ingest pipeline
      retrieval/    # embeddings, vector store, BM25, hybrid fusion, reranking
      generation/   # prompts, LLM client, confidence scoring, faithfulness checking
      db/           # Postgres models (audit log, feedback)
      api/          # /query, /ingest, /feedback routes
    tests/          # unit + integration tests (all passing, runs offline)
    requirements.txt
    Dockerfile
  data/sample_corpus/   # the 12-doc synthetic cardiology corpus, ingestable as-is
  scripts/
    load_sample_corpus.py   # loads the sample corpus into a running instance
    ingest_pubmed.py        # real PubMed ingestion via NCBI E-utilities
  docker-compose.yml   # Postgres + Qdrant + Redis + backend
  .env.example
```

## Running it

**Fastest path (no Docker, in-memory everything):**
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env       # then fill in ANTHROPIC_API_KEY
PYTHONPATH=. uvicorn app.main:app --reload
```
Then in another shell:
```bash
python ../scripts/load_sample_corpus.py
curl -X POST localhost:8000/query -H "Content-Type: application/json" \
  -d '{"query": "How long should DAPT continue after PCI?"}'
```

**Full stack (real Postgres + Qdrant):**
```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY, set VECTOR_BACKEND=qdrant
docker compose up --build
```

**Run tests:**
```bash
cd backend && PYTHONPATH=. pytest -v
```
9/9 passing as of this build, covering chunking, confidence scoring, and full ingest→retrieve integration.

## Immediate next steps (in priority order)

1. **Swap in a real embedding provider** (`openai` or `voyage` in `.env`) — this is the single highest-leverage upgrade; the hash stub only captures lexical overlap, not semantic meaning.
2. **Swap in a real cross-encoder reranker** — same reasoning.
3. **Auth** — JWT/OIDC on every endpoint before this touches anything resembling real clinical use.
4. **Golden evaluation set** — 20-30 clinician-validated cardiology Q&A pairs to start measuring retrieval precision, citation faithfulness, and confidence calibration numerically instead of by eyeballing responses.
5. **Real corpus at scale** — run `scripts/ingest_pubmed.py` against real cardiology queries, then add NICE/WHO/CDC/DailyMed ingestion scripts following the same pattern.
6. **Frontend** — a real app talking to this API (the HTML prototype's UI patterns — citation chips, confidence breakdown, evidence sidebar — are worth carrying over).
