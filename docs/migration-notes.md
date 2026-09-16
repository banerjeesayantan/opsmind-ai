# OpsMind AI - Migration Notes

## Step 1 - Foundation Cleanup

### Removed
- DuckDuckGo generic web search (`app/core/langgraph/tools/duckduckgo_search.py`, and its registration in `tools/__init__.py`)
- mem0 personal long-term memory (initialization, retrieval, and update calls in `app/core/langgraph/graph.py`, and the dead `LONG_TERM_MEMORY_*` settings in `app/core/config.py`)
- Dependencies confirmed unused after a full repo import-graph scan: `duckduckgo-search`, `langchain-community`, `mem0ai`, and `ddgs` (the renamed duckduckgo-search package - found unused, not part of the original three-item removal list, added after inspection)

### Fixed
- `uvloop` made Windows-safe two ways: a `sys_platform != 'win32'` marker in `pyproject.toml` so Poetry doesn't try to build it there (it has no Windows wheels - wraps libuv's POSIX-only event loop), and the `Makefile`'s three hardcoded `--loop uvloop` flags (`prod`, `staging`, `dev`) changed to `--loop auto`, so uvicorn uses uvloop when installed and falls back to asyncio when it isn't, with no code duplication
- `docker-compose.yml` database image swapped from `pgvector/pgvector:pg16` to plain `postgres:16` - pgvector's only consumer was mem0, confirmed via repo-wide grep for `pgvector`/`CREATE EXTENSION` before changing

### Rebranded
- `pyproject.toml` / `app/core/config.py` / `.env.example`: `PROJECT_NAME` -> "OpsMind AI", `DESCRIPTION` -> incident-platform description, `POSTGRES_DB` default -> `opsmind` (was the leftover `food_order_db` / `mydb` / `Web Assistant` - evidence this repo was cloned from an untouched generic multi-purpose FastAPI/LangGraph template, not an existing incident-response system)
- `Makefile`: stale `docker build -t fastapi-langgraph-template` -> `opsmind-ai`

### Preserved (unchanged in this step)
- FastAPI application structure and middleware
- Authentication (`app/api/v1/auth.py`, `app/models/user.py`)
- PostgreSQL / SQLModel infrastructure (`app/services/database.py`, `app/models/session.py`)
- LLM service reliability layer (`app/services/llm.py`) - retry + circular model fallback, reused as-is later
- Langfuse integration
- Prometheus / Grafana scaffolding
- Docker / Docker Compose foundation

### Known pre-existing issue (not introduced by this step)
`pyproject.toml` declares `requires-python = ">=3.13"`, but the upstream README lists "Python 3.11+" as a prerequisite. These two sources disagree. This step did not touch either the Python version constraint or the README's prerequisites table - flagged here for visibility, to be resolved deliberately rather than silently.

### Next
Incident domain model, telemetry interfaces, and the real investigation LangGraph. Not started in this step.
## Step 2 - Agent 2: Approval → Action → Verification → Evaluation → API (Phases 3-8)

Picked up after the investigation LangGraph (Evidence → Diagnosis) and the
full domain model already existed. The Remediation Planner LangGraph node
(`app/investigation/nodes/remediation_planner.py` + a `RemediationCandidate`
schema) is a separate, in-progress workstream and was not touched here.

### Added
- **Persistence layer** (`app/services/persistence.py`) - this didn't exist
  yet despite being a stated architecture rule ("nodes/routes don't write
  the DB directly"). `IncidentPersistenceService` is now the single,
  regression-tested place every `app.models.*` incident row gets written:
  incident CRUD, investigation-result persistence (Evidence/Hypothesis/
  Diagnosis), remediation + approval workflow, action execution, and
  verification. Constructed with an injectable SQLAlchemy engine so the
  exact same code path is tested against a real database (real Postgres in
  `tests/conftest.py`'s `test_engine` fixture, with an in-memory SQLite
  fallback) rather than mocked.
- **Phase 3 - Risk + Approval**: `app/investigation/risk.py`
  (`classify_risk`, `requires_human_approval` - deterministic, no LLM call)
  plus the approval workflow in the persistence layer.
- **Phase 4 - Controlled Action**: `app/investigation/action_executor.py`
  (`ControlledActionExecutor`) - simulated execution for all four
  `RemediationActionType` branches, each validating its own parameters.
- **Phase 5 - Verification**: `app/investigation/verification.py`
  (`VerificationService`) - fresh-telemetry-vs-baseline comparison with a
  deterministic recovery threshold.
- **Phase 6 - Observability**: incident-specific Prometheus metrics
  (`opsmind_*`, in `app/core/metrics.py`), recorded directly from
  `IncidentPersistenceService`'s write methods.
- **Phase 7 - API**: `app/api/v1/incidents.py` - the full incident lifecycle
  as REST endpoints (create, investigate, recommend remediation, approve/
  reject, execute, verify, get results, timeline), wired into
  `app/api/v1/api.py` under `/api/v1/incidents`. Swagger (`/docs`) is the
  demo UI, per project convention - no separate frontend was built.
- **Phase 8**: this note, `README.md` rewritten from the inherited generic
  template content to describe OpsMind, and `docs/incident-flow.md` added
  as a full pipeline walkthrough.

### Fixed along the way
- A naive/aware `datetime` subtraction bug surfaced by the
  `opsmind_incident_time_to_resolution_seconds` metric (SQLite and
  Postgres round-trip timezone awareness differently) - resolved by
  normalizing both sides to naive UTC before subtracting.

### Verified for real
92 tests pass (`uv run pytest tests/ -v`), including persistence tests run
against a real local PostgreSQL 16 instance (not sqlite-only, not mocked)
and API tests run through real HTTP via FastAPI's `TestClient`. The one
component faked in tests is the investigation graph's underlying LLM call
(Groq) - this sandbox has no network path to Groq's API, and a live LLM
call would make tests non-deterministic regardless, so the graph nodes are
tested with fakes exactly as `HypothesisGeneratorNode` et al. already were.

### Discrepancy noted, not silently resolved
The task brief this step started from described "51 tests passing" and a
completed persistence layer as prior work. Neither was present in the
repository at the start of this step - only `tests/test_telemetry.py` (15
tests) existed, and no `app/services/persistence.py`. This is flagged here
rather than assumed away, since it affects what "already done" means for
whoever picks this up next.

### Next
Wire the (separately-developed) `remediation_planner` LangGraph node into
`app/investigation/graph.py` once it lands, calling
`IncidentPersistenceService.persist_remediation` with the fields it
produces - no other change to this step's code should be required, since
Phase 3 onward was deliberately built against the persisted `Remediation`
row rather than the planner's internal candidate representation.
