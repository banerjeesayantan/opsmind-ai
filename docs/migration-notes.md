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