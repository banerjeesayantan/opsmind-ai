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

## Step 3 - Production-readiness audit fixes (A1-A3, B1) + backend completion

Picked up after `remediation_planner` was integrated (Step 2's "Next"
above) and the pipeline was committed as `c8f480f`. This step worked
from a consolidated audit (A1-A3, B1) plus a backend-completion
checklist, both supplied by a parallel review pass.

### A1 - graph.ainvoke() -> InvestigationState boundary
Verified already correct (`InvestigationState.model_validate(result)` in
`app/api/v1/incidents.py`). No change needed.

### A2 - diagnosis/hypothesis mismatch -> NOT NULL crash
Confirmed real by direct reproduction against real Postgres: a
client-supplied `diagnosis_id` that doesn't exist, or belongs to a
different incident, reached `persist_remediation()` unchecked and raised
a raw `IntegrityError` (foreign-key violation) - a 500, not a clean
error. Fixed: added `IncidentPersistenceService.get_diagnosis()` and had
`POST /incidents/{id}/remediations` validate existence + incident
ownership before ever calling `persist_remediation()`, returning `404`
instead. Regression tests added at both the persistence layer
(`tests/test_persistence.py`) and the API layer
(`tests/test_api_incidents.py`).

Side finding while adding a persistence-layer regression test for this:
SQLite doesn't enforce foreign keys by default, unlike Postgres, so the
same bad-FK test would silently succeed on the SQLite fallback engine
instead of raising - `tests/conftest.py`'s fallback engine now enables
`PRAGMA foreign_keys=ON` so its behavior matches Postgres for constraint
violations. This exposed that one existing test
(`tests/test_engine_fixture.py`) created only a partial schema (missing
the `user` table that `incident.created_by` references) - fixed to
create the full schema, matching real usage.

### A3 - eager import-time initialization
Confirmed real and fixed: `DatabaseService.__init__` called
`SQLModel.metadata.create_all(self.engine)` eagerly, forcing a live
Postgres round-trip merely to import `app.services` (imported
transitively by almost everything). Verified directly: with Postgres
stopped, even `tests/test_risk.py` (which touches no database code at
all) failed at collection before this fix, and passed cleanly after it.
Removed the eager `create_all()` call - schema is already managed by
Alembic migrations, so this was redundant as well as harmful.
`create_engine()` itself remains lazy; a real connection now only opens
on first actual use, which is where a "database unreachable" error
belongs. Verified DB-dependent code still fails correctly (just later)
when Postgres is genuinely down.

`LLMRegistry`'s eager construction was verified separately and left
unchanged: it only validates that `GROQ_API_KEY` is a non-empty string
(sub-second, no network call), a fundamentally different risk profile
from a live external database dependency. Documented as intentional
fail-fast behavior, not a bug.

### B1 - python-jose dependency audit
Resolved version verified directly against the real Poetry environment:
`python-jose==3.5.0` (the latest available release). Two real,
documented issues exist in the dependency chain:
- CVE-2024-33663's fix (3.4.0) has a documented bypass via DER-encoded
  keys, still present in 3.5.0 (no newer version exists, and no formal
  CVE/GHSA entry for the bypass itself as of this audit - found via
  independent security research, not in `pip-audit`'s database).
- `ecdsa` (a transitive dependency of `python-jose[cryptography]`) has
  an open, upstream-declined advisory (PYSEC-2026-1325 / CVE-2024-23342,
  a timing side-channel on ECDSA signing/key-generation - verification
  is unaffected, and the ecdsa maintainers have stated no fix is
  planned).

Neither is exploitable in this application: OpsMind only ever uses
HS256 with a single symmetric secret - no RSA/EC keypair exists anywhere
in the codebase, and `jwt.decode()` is called with an explicit
single-value `algorithms=[...]` allowlist, so a token declaring a
different algorithm is rejected outright regardless of either issue.
`ecdsa`'s vulnerable signing/key-generation code path is never invoked
(this app never performs ECDSA operations). Dependency left unchanged
per the audit's own guidance ("do not invent an upgrade if 3.5.0 is
already the latest available version"). Added
`tests/test_jwt_security.py` as regression coverage for the actual
protective mechanism (algorithm allowlist, secret mismatch, `alg: none`,
expiry) rather than for the vulnerabilities themselves, since they have
no foothold here to reproduce.

### Backend completion checklist
- **API surface**: added the one genuinely missing piece,
  `GET /incidents/{id}/evidence` (raw observed evidence - logs, metrics,
  deployments - independent of any hypothesis/diagnosis built from it),
  reusing the already-existing but previously-unused
  `IncidentPersistenceService.list_evidence()`. Everything else in the
  checklist (create, investigate, get, timeline, remediation, approval,
  execute, verify, list) already existed.
- **Authentication on incident routes**: deliberately NOT added in this
  step, despite `app/api/v1/auth.py` already having a reusable
  `get_current_user` dependency. Wiring it onto every incident route
  would break all ~30 existing tests that call these routes directly
  (none send auth headers) and would reverse this project's
  consistently-documented design across every prior step - Swagger
  (`/docs`) as an open demo interface, no login required. Flagged here
  as a real, deliberately deferred gap rather than silently skipped or
  hastily redesigned at the very end of a pass.
- **Full lifecycle E2E**: added
  `test_full_lifecycle_reaches_resolved_status` - not a new happy-path
  test from scratch, but the existing
  `test_investigate_persists_graph_remediation_and_feeds_existing_approval_flow`'s
  exact request sequence plus the one assertion that test intentionally
  leaves open (final incident status), using a deterministic
  verification-service override so the assertion doesn't depend on
  mock-telemetry chance.
- **Database/migrations**: verified clean - `alembic current` matches
  `alembic heads` (`1f8f0634d544`), and `alembic check` reports no model/
  migration drift.
- **Observability**: verified `/metrics` serves real Prometheus text
  (HTTP 200) via a live server boot, not just unit tests.
- **CI**: existing workflow verified still correct; one comment fixed
  for accuracy (it described the pre-A3-fix eager-connect behavior).
- **Grafana / expanded docs**: explicitly deprioritized per this step's
  own instructions ("lower priority than critical backend work") and not
  attempted here - a genuinely deferred item, not a silent omission.

### Verified
`poetry run pytest tests/ -v`: 134 passed, 0 failed, 0 errors, 1 warning
(pre-existing, unrelated). `pip-audit` run against the real Poetry-resolved
dependency set (not an empty/wrong requirements file - confirmed this
distinction mattered during the audit). `alembic check`: no drift.
Live server boot: `/metrics` returns 200 with real Prometheus text.
