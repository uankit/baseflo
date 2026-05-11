# Baseflo Server

The Python FastAPI engine + agent runtime + connector framework.

Status: M0 (foundation reset) — see [`../docs/31-todolist.md`](../docs/31-todolist.md).

## Quickstart

The server expects two services available locally: **Postgres 15+** and **Redis 7+**.
You can either bring your own (already running natively) or use the bundled
`docker-compose.dev.yml`.

### Option A — use your existing local Postgres / Redis (recommended if you have them)

```bash
# 1. Create two databases on your local Postgres — one for dev, one for tests.
psql -h localhost -U postgres -c "CREATE DATABASE baseflo;"
psql -h localhost -U postgres -c "CREATE DATABASE baseflo_test;"

# Postgres extensions the migrations require (one-time per database):
psql -h localhost -U postgres -d baseflo      -c "CREATE EXTENSION IF NOT EXISTS citext; CREATE EXTENSION IF NOT EXISTS pgcrypto;"
psql -h localhost -U postgres -d baseflo_test -c "CREATE EXTENSION IF NOT EXISTS citext; CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 2. Install Python deps (uv recommended):
uv sync --all-extras
# or: pip install -e ".[dev]"

# 3. Copy env and edit BASEFLO_DATABASE_URL / BASEFLO_REDIS_URL to match your setup:
cp .env.example .env

# 4. Run migrations against the dev database:
alembic upgrade head

# 5. Run the dev server:
uvicorn app.main:app --reload --port 8000

# 6. Health check:
curl http://localhost:8000/api/v1/health
```

For tests, set `BASEFLO_DATABASE_URL` in your shell (or a `.env.test`) to your
**test** database, then run `pytest -m integration`.

### Option B — bundled Docker compose (zero local config)

```bash
docker compose -f ../docker-compose.dev.yml up -d
# Postgres dev:  localhost:5432   (user/pass: baseflo/baseflo, db: baseflo)
# Postgres test: localhost:5433   (user/pass: baseflo/baseflo, db: baseflo_test)
# Redis:         localhost:6379

cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
# Unit + integration:
pytest

# With coverage:
pytest --cov

# Lint + types:
ruff check .
ruff format --check .
mypy app
lint-imports
```

## Layout (per [`../docs/01-architecture.md`](../docs/01-architecture.md))

```
app/
├── main.py                # FastAPI app + lifespan
├── core/                  # config, errors, ids, context, crypto
├── observability/         # logging, tracing, metrics
├── api/v1/                # FastAPI routes
├── services/              # use-case orchestration
├── orchestration/         # generation/refinement sagas, jobs
├── agents/                # Pydantic AI specialists + runtime
├── engines/               # deterministic compilers (schema, analytics, exports, ...)
├── repositories/          # database access
└── db/                    # SQLAlchemy models, session
migrations/                # alembic
tests/                     # unit + integration
```

Coding rules: [`../docs/05-coding-rules.md`](../docs/05-coding-rules.md). TDD-first, no regex/heuristics, typed everything.
