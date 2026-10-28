# Agent Memory Platform

Persistent memory for AI agents: episodic, semantic and procedural memory in
one typed, scoped, auditable service.

## The enterprise problem

Stateless agents forget. A support or operations agent that cannot recall past
interactions, distilled facts, or proven routines repeats mistakes, contradicts
itself, and leaks one user's context into another's session. Bolting on a raw
vector store does not solve this: it gives retrieval without provenance,
conflict handling, decay, or tenant isolation — the properties production
systems actually get audited on.

This platform provides the memory layer an enterprise agent needs: three
memory kinds, per-scope isolation, confidence + provenance on facts, a
consolidation pipeline that turns raw interaction history into durable
knowledge, importance/recency scoring with pruning, conflict supersession
with a full audit trail, and secret/PII-like redaction at write time.

## Architecture overview

```
                     ┌─────────────────────────┐
                     │  FastAPI layer (api.py) │  optional
                     └────────────┬────────────┘
                                  ▼
                     ┌─────────────────────────┐
                     │  MemoryService          │  orchestration
                     │  (service.py)           │  redact → store → audit
                     └────┬──────┬──────┬─────┘
                          ▼      ▼      ▼
              ┌──────────┐ ┌──────────┐ ┌──────────────┐
              │ retrieval│ │consolida-│ │ scoring /    │
              │ (scoped, │ │tion      │ │ redaction    │
              │ ranked)  │ │epi→sem.  │ │              │
              └────┬─────┘ └────┬─────┘ └──────────────┘
                   ▼            ▼
              ┌─────────────────────────────────┐
              │ Stores: InMemory / JSON file  │
              └─────────────────────────────────┘
```

See `docs/architecture.md` for the full description and diagram.

### Memory kinds

| Kind | What it holds | Example |
| --- | --- | --- |
| Episodic | Timestamped interaction records | "User asked about refund policy" |
| Semantic | Facts with confidence + provenance | `refund-policy / window-days / 30 days` (0.9) |
| Procedural | Reusable skills with success rates | `refund-lookup`: steps + 2/3 success |

### Key behaviours

- **Scoped retrieval:** a record is visible only to its exact
  tenant + user + agent scope. No wildcard fallback.
- **Conflict handling:** adding a fact with the same subject + predicate
  supersedes the old one; the old fact is retained with `superseded_by` and
  an audit entry. History is never rewritten.
- **Consolidation:** topics with ≥ 2 episodic records produce a semantic fact
  whose provenance lists every contributing record.
- **Scoring & decay:** recency decays exponentially (30-day half-life);
  combined score weights importance (0.6) over recency (0.4).
- **Pruning:** only stale (default > 90 days) *and* low-importance
  (< 0.3) episodic records are pruned; important history survives.
- **Redaction:** bearer tokens, labelled secrets, API-key shapes, SSNs,
  card numbers, emails and phone numbers are replaced at write time, so raw
  secrets never persist.

## How to run

```bash
# Core + demo (stdlib only, no install needed)
python3 demo.py

# Tests
python3 -m pytest -q

# API service (optional; needs fastapi + uvicorn)
pip install -r requirements.txt
uvicorn app:app --reload
# POST /episodic, POST /facts, GET /retrieve, POST /consolidate
```

Environment (see `.env.example`): `MEMORY_STORE_PATH`,
`MEMORY_RETENTION_DAYS`, `MEMORY_MIN_IMPORTANCE`, `MEMORY_HALF_LIFE_DAYS`.

## Key design decisions and trade-offs

- **Core is stdlib-only.** The memory logic has no framework dependency, so
  it is testable anywhere and portable into any agent runtime; FastAPI is an
  optional thin shell, and its tests skip when it is absent.
- **Exact-scope isolation over hierarchical fallback.** Simpler to audit and
  impossible to leak across users by accident; the cost is that shared
  tenant-level knowledge must be written explicitly per scope.
- **Supersession instead of overwrite or version chains.** One live fact per
  claim, old versions retained for audit — readable, debuggable, and enough
  for most agent workloads; a full version graph would add complexity without
  a demonstrated need.
- **Deterministic consolidation, not LLM summarisation.** Grouping by topic
  tag with provenance is reproducible and testable; an LLM summariser can be
  plugged in later as a consolidation strategy without changing the model.
- **JSON file store, not a database.** Sufficient for a portfolio-grade
  reference implementation and easy to inspect; a production deployment
  would swap in a real store behind the same `InMemoryStore` interface.

## What it demonstrates

Multi-kind agent memory design, scope-based multi-tenancy, conflict
resolution with auditability, decay/pruning policy design, write-time
redaction, deterministic consolidation, and a clean service/store/API
separation — the pieces interviewers probe when they ask how an agent
"remembers" safely in production.

## Project layout

```
src/agent_memory/  models, stores, scoring, redaction, consolidation,
                   retrieval, service, api (FastAPI, optional)
app.py             FastAPI entrypoint
demo.py            end-to-end demo (stdlib only)
tests/             pytest coverage of core logic + API (skipped w/o FastAPI)
docs/architecture.md, docs/github-actions-ci.yml
requirements.txt, .env.example, Dockerfile
```

All code is original; all demo data is synthetic and generic.
