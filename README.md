# OpsMind AI

**AI-powered incident investigation and response platform.**

OpsMind takes an incident from "something is wrong" to "here's what happened,
here's the fix, and here's proof it worked" - automatically investigating,
diagnosing, recommending a remediation, gating risky actions behind human
approval, executing the fix, and verifying recovery.

```
Incident → Evidence → Timeline → Hypotheses → Validation → Impact → Diagnosis
        → Remediation → Approval → Action → Verification
```

Built with **FastAPI**, **LangGraph**, **SQLModel/PostgreSQL**, and the
**Groq free tier** as the default $0 LLM provider. See
[docs/incident-flow.md](docs/incident-flow.md) for a full walkthrough of the
pipeline and how it maps to the API.

---

## Table of Contents

- [OpsMind AI](#opsmind-ai)
  - [Table of Contents](#table-of-contents)
  - [Project status](#project-status)
  - [Prerequisites](#prerequisites)
  - [Getting started](#getting-started)
    - [1. Environment setup](#1-environment-setup)
    - [2. Install dependencies](#2-install-dependencies)
    - [3. Start PostgreSQL and run migrations](#3-start-postgresql-and-run-migrations)
    - [4. Run the tests](#4-run-the-tests)
    - [5. Run the application](#5-run-the-application)
  - [Using the API](#using-the-api)
  - [Observability](#observability)
  - [Architecture rules](#architecture-rules)
  - [Tech stack](#tech-stack)

---

## Project status

| Phase | Scope | Status |
|---|---|---|
| 1 | Domain model, PostgreSQL, Alembic migrations | ✅ Done |
| 2 | Investigation LangGraph (Evidence → Timeline → Hypotheses → Validation → Impact → Diagnosis) | ✅ Done |
| 2b | Remediation Planner (`remediation_planner` node) | 🚧 In progress (separate workstream) |
| 3 | Risk classification + Approval workflow | ✅ Done |
| 4 | Controlled (simulated) action execution | ✅ Done |
| 5 | Post-action verification | ✅ Done |
| 6 | Observability (Prometheus metrics) | ✅ Done |
| 7 | FastAPI incident endpoints | ✅ Done |
| 8 | Full test suite, docs | ✅ Done (this document + [docs/incident-flow.md](docs/incident-flow.md)) |

The `remediation_planner` LangGraph node (Phase 2b) - which turns a
confirmed `Diagnosis` into a proposed `RemediationCandidate` via an LLM call
- is being developed independently. Everything from Phase 3 onward
(risk classification, approval, execution, verification, and the API) is
built against the persisted `Remediation` row and doesn't depend on that
node's internal representation, so either can be developed and tested in
isolation. Until the planner lands, remediations can be recommended directly
via `POST /api/v1/incidents/{id}/remediations` (see below) - this is also
useful for demoing the pipeline end-to-end from Swagger without needing an
LLM call at all.

## Prerequisites

| Tool | Purpose |
|---|---|
| [Python 3.13+](https://www.python.org/downloads/) | Runtime |
| [uv](https://docs.astral.sh/uv/) | Dependency management (`pip install uv`) |
| [PostgreSQL 16](https://www.postgresql.org/) | Primary data store - via Docker (`docker-compose up -d db`) or a local install |
| A free [Groq API key](https://console.groq.com/keys) | $0 default LLM provider - no credit card required |

OpenAI is **optional** and only used if `OPENAI_API_KEY` is set - a fresh
checkout never depends on a paid API.

---

## Getting started

### 1. Environment setup

Copy `.env.example` to `.env` and fill in the values - at minimum, a real
`GROQ_API_KEY` (get one free at [console.groq.com/keys](https://console.groq.com/keys))
and matching Postgres credentials.

```bash
cp .env.example .env
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Start PostgreSQL and run migrations

Via Docker:

```bash
docker-compose up -d db
```

...or point `POSTGRES_HOST`/`POSTGRES_PORT` in `.env` at a local Postgres
instance. Either way, then apply migrations:

```bash
uv run alembic upgrade head
```

### 4. Run the tests

```bash
uv run pytest tests/ -v
```

Persistence-layer tests use a dedicated `opsmind_test` database
(`OPSMIND_TEST_DATABASE_URL`, default
`postgresql+psycopg2://postgres:postgres@localhost:5432/opsmind_test`) so
they never touch your main `opsmind` data, and fall back automatically to an
in-memory SQLite engine if that database isn't reachable - so the suite
still runs even without a dedicated test database, though real Postgres is
the intended path. Every persistence and API test exercises real SQL
against a real relational database - nothing about the persistence layer
itself is mocked.

### 5. Run the application

```bash
uv run uvicorn app.main:app --reload
```

Interactive API docs (Swagger UI) - **the intended demo UI, no separate
frontend needed** - are then available at:

**http://127.0.0.1:8000/docs**

---

## Using the API

All incident endpoints live under `/api/v1/incidents`. A typical walkthrough
from Swagger:

1. **`POST /incidents`** - open an incident (`title`, `service`, `severity`).
2. **`POST /incidents/{id}/investigate`** - run the investigation graph for
   a `service` + time window; persists evidence, timeline, hypotheses, and
   (if reached) a diagnosis.
3. **`POST /incidents/{id}/remediations`** - recommend a remediation for the
   diagnosis (`action_type` + `parameters`). Risk is always classified
   server-side (`app.investigation.risk.classify_risk`), never trusted from
   the client, and an `Approval` row is opened automatically.
4. **`GET /incidents/{id}/approvals`** / **`POST
   /incidents/{id}/approvals/{approval_id}/decision`** - review and
   approve/reject. LOW risk is auto-approved (`NOT_REQUIRED`); MEDIUM/HIGH
   block here until a human decides.
5. **`POST /incidents/{id}/remediations/{remediation_id}/execute`** -
   simulate the action (rejected with `409` unless approved/auto-approved).
6. **`POST /incidents/{id}/executions/{execution_id}/verify`** - collect
   fresh telemetry and compare it against the incident's original evidence
   to decide whether it actually recovered.
7. **`GET /incidents/{id}`** - the full picture: hypotheses, diagnosis,
   remediations, approvals, executions, verifications.
8. **`GET /incidents/{id}/timeline`** - the append-only chronological record
   of everything that happened.

See [docs/incident-flow.md](docs/incident-flow.md) for the full pipeline
walkthrough, including the deterministic risk rules and recovery criteria.

---

## Observability

Prometheus metrics are exposed at `/metrics`, including OpsMind-specific
counters/histograms (prefixed `opsmind_`) alongside the generic HTTP/LLM
metrics: `opsmind_investigations_completed_total`,
`opsmind_diagnosis_confidence`, `opsmind_remediations_by_risk_total`,
`opsmind_approvals_total`, `opsmind_action_executions_total`,
`opsmind_verifications_total`, and
`opsmind_incident_time_to_resolution_seconds`. These are recorded from
`IncidentPersistenceService` - the single choke-point every incident state
transition passes through - so every metric reflects a real, persisted
event rather than an in-flight/uncommitted one.

A separate, generic LLM-response evaluation suite (Langfuse + an
LLM-as-a-judge, inherited from the project's upstream template) also exists
under `evals/` - see that module's own docs for running it. It evaluates
conversational LLM output quality generally and is not incident-pipeline
specific.

---

## Architecture rules

These hold across the whole codebase, not just one phase:

- **$0 by default.** Groq's free tier is the default LLM provider; OpenAI is
  opt-in only. Controlled actions are always simulated (`ExecutionStatus.SIMULATED`),
  never calling a real orchestrator.
- **Injectable dependencies.** Every LangGraph node, the persistence
  service, the action executor, and the verification service take their
  collaborators (an LLM, a telemetry service, a DB engine) via the
  constructor, defaulting to the real/$0 implementation - so every layer is
  testable with a fake, with no network or database required for unit
  tests.
- **Evidence references are validated, never hallucinated.** Every
  hypothesis, diagnosis, and verification traces back to a real evidence
  item; anything an LLM cites that doesn't resolve to real data is dropped.
- **Nodes/routes never write the database directly.** All writes to
  `app.models.*` go through `app.services.persistence.IncidentPersistenceService`
  - the one place that's regression-tested for real, real-SQL persistence
  behavior.
- **Risk classification is deterministic, not an LLM call.** Given the same
  action type and parameters, `classify_risk` always returns the same
  answer - it's the safety gate that decides whether a human must approve
  an action before it can run.
- **Tests are plain sync functions.** Async APIs are driven via
  `asyncio.run()` from ordinary `def test_...():` functions - no
  `pytest-asyncio` dependency.

---

## Tech stack

- **[FastAPI](https://fastapi.tiangolo.com/)** - API framework (Swagger UI as the demo surface)
- **[LangGraph](https://langchain-ai.github.io/langgraph/)** - Investigation pipeline orchestration
- **[SQLModel](https://sqlmodel.tiangolo.com/) / SQLAlchemy** - ORM and database management
- **[PostgreSQL](https://www.postgresql.org/)** - Primary data store
- **[Groq](https://groq.com/)** - $0 default LLM provider (OpenAI optional)
- **[Prometheus](https://prometheus.io/) / [Grafana](https://grafana.com/)** - Metrics and dashboards
- **[uv](https://docs.astral.sh/uv/)** - Python dependency management
