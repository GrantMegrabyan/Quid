# Quid

A self-hosted personal expense tracker. Import your bank statements, let AI sort
them into categories, write rules to automate the boring parts, and link Amazon
charges back to what you actually bought — all running on your own machine,
backed by a single SQLite file.

Quid is a monorepo with two parts:

- **`api/`** — a [FastAPI](https://fastapi.tiangolo.com/) + SQLite backend
  (Python, managed with [`uv`](https://docs.astral.sh/uv/)).
- **`webui/`** — a [SvelteKit](https://svelte.dev/) frontend
  (TypeScript + Tailwind, managed with `npm`).

## Features

- 📥 **Flexible import** — upload bank CSVs (Monzo, Revolut, and friends; headers
  are matched case-insensitively), add transactions one at a time, or paste
  free-form text like `coffee 3.50 yesterday, Tesco 42 on the 3rd` and let AI turn
  it into transactions. Every import is a review-before-save **preview → confirm**
  flow, and re-importing the same file is a safe no-op (idempotent dedup).
- 🤖 **AI categorisation** — parsed transactions are sorted into your categories
  automatically via [OpenRouter](https://openrouter.ai/). It strongly prefers your
  existing categories and only invents a new one when nothing fits. Toggleable.
- 📜 **Import rules** — match transactions by name / amount / date / day-of-month
  and either exclude them or categorise them (optionally rewriting their display
  name and note). Dry-run any rule with **Preview matches** before saving it.
- 📦 **Amazon order matching** — import your Amazon order history (CSV *or* a
  privacy-preserving browser bookmarklet that scrapes orders locally and never
  sends your Amazon credentials to Quid) and Quid links each charge to what it
  bought, generates a short description, and replaces the coarse "Shopping" bucket
  with a precise per-order category.
- 📊 **Dashboard** — monthly totals with month-over-month change, top category,
  transaction counts and averages, plus the full transaction list and charts.
- 🔒 **Production-ready hardening** — fail-fast config validation, locked-down
  CORS and trusted hosts, optional security headers, and a triple-guarded
  destructive testing router that can never point at a real database by accident.

## Quickstart

You'll need [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and
[Node.js](https://nodejs.org/) (with `npm`).

**1. Start the backend** (from `api/`):

```sh
cd api
uv sync
uv run quid-api migrate       # create / upgrade the SQLite schema
uv run quid-api seed --reset  # load deterministic sample data (optional)
uv run quid-api serve --reload
```

The API listens on `http://localhost:8000`; interactive docs are at
`http://localhost:8000/docs`.

**2. Start the frontend** (from `webui/`, in a second terminal):

```sh
cd webui
npm install
cp .env.example .env
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`). The web UI talks to
the API at `VITE_API_BASE_URL` (default `http://localhost:8000`).

### Enabling AI features

AI categorisation, AI free-form import, and Amazon short names all call
OpenRouter. Set a key for the backend:

```sh
# api/.env
QUID_OPENROUTER_API_KEY=sk-or-...
```

The two AI toggles (`aiCategorizeEnabled`, `aiShortNamesEnabled`) live on the
**Settings** page and both default on. Without a key, the AI-dependent flows
return an error; everything else works fine.

## Configuration

The backend is configured entirely through `QUID_`-prefixed environment variables
(or an `api/.env` file) — database URL, CORS/host allow-lists, the OpenRouter
model, production mode, and more. See **[`api/README.md`](api/README.md)** for the
full table and the production-hardening guide.

## Project structure

```
quid/
├── api/      FastAPI + SQLite backend, CLI, Alembic migrations  → api/README.md
└── webui/    SvelteKit frontend                                 → webui/README.md
```

For everything beyond getting it running — every endpoint, the CSV/free-form
import semantics, import rules, the Amazon bookmarklet, the money-as-decimal-strings
transport contract, and the CLI — read the two component READMEs:

- **[`api/README.md`](api/README.md)** — backend, API, configuration, CLI.
- **[`webui/README.md`](webui/README.md)** — frontend setup, pages, and the
  Amazon browser-import workflow.

## Development

```sh
# Backend (from api/)
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest

# Frontend (from webui/)
npm run check
npm run build
npm run test:e2e   # Playwright e2e against a throwaway test database
```

Backend data is stored in `api/.data/quid.db` by default; schema changes go through
[Alembic](https://alembic.sqlalchemy.org/) migrations under `api/alembic/versions/`.
The Playwright suite boots its own isolated API and database, so it's safe to run
repeatedly.
