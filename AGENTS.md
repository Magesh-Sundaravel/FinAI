# AGENTS.md

## Purpose

This repository is a finance-tracking monorepo with:

- `backend/`: FastAPI API, SQLModel data layer, spreadsheet and OCR ingestion, and the finance chat agent.
- `frontend/`: React 19 + Vite single-page app that consumes the backend API.
- `.github/workflows/`: Cloud Run deployment pipeline.
- `.agents/`: local agent-oriented hooks and repo-specific skills.

Use this file as the operating guide for code agents working in this repo.

## Repository Map

### Backend

Key files:

- `backend/app/main.py`: FastAPI entrypoint, router registration, static frontend serving, `/api/health`.
- `backend/app/db.py`: env loading, async database engines, SQLite fallback, session factories, lightweight schema migration for `expenses.user_id`.
- `backend/app/models.py`: `User` and `Expense` SQLModel tables.
- `backend/app/auth.py`: current-user resolution from `X-Goog-Authenticated-User-Email`, with `DEV_USER_EMAIL` fallback for local development.
- `backend/app/api/endpoints/expenses.py`: CRUD, spreadsheet upload, OCR upload, summary/profile endpoints.
- `backend/app/api/endpoints/agent.py`: chat endpoint, LangGraph path when `GEMINI_API_KEY` exists, rule-based fallback when it does not.
- `backend/app/agent/graph.py`: LangGraph ReAct loop and tool wiring.
- `backend/app/agent/tools.py`: framework-agnostic query tools and read-only SQL guardrails.
- `backend/tests/agent/test_tools.py`: current test coverage focuses on backend agent tool safety and query behavior.

### Frontend

Key files:

- `frontend/src/App.tsx`: main application UI, API calls, demo fallback mode, chat UX.
- `frontend/src/App.css` and `frontend/src/index.css`: primary styling.
- `frontend/package.json`: Vite scripts and frontend dependencies.

### Deployment

- `backend/Dockerfile`: multi-stage build; builds the React app, then serves it from FastAPI static files.
- `.github/workflows/deploy.yml`: builds and deploys the unified container to Google Cloud Run on pushes to `main` and `v*` tags.

## Architecture Notes

- The backend serves both JSON API routes and the built frontend assets in production.
- Local backend storage defaults to SQLite at `backend/data/expenses.db` when `DATABASE_URL` is unset.
- Production is intended for PostgreSQL/Cloud SQL, with a separate `READONLY_DATABASE_URL` for text-to-SQL agent queries.
- User isolation is central to the backend design. Expense rows are scoped by `user_id`, and agent SQL must include the requesting user's ID.
- The chat agent has two modes:
  - `GEMINI_API_KEY` present: LangGraph + Gemini-backed tool-using agent.
  - `GEMINI_API_KEY` absent: local rule-based fallback in `backend/app/api/endpoints/agent.py`.
- Receipt image uploads prefer GCS when `GCS_BUCKET_NAME` is configured; otherwise they fall back to local files under `backend/data/uploads`.
- The frontend falls back to demo data if the backend is unreachable.

## Development Commands

Run commands from the relevant subdirectory.

### Backend

Start dev server:

```bash
cd backend
uv run uvicorn app.main:app --port 8000 --reload
```

Run tests:

```bash
cd backend
uv run pytest
```

Lint Python:

```bash
cd backend
uv run ruff check .
```

Type-check Python:

```bash
cd backend
uv run mypy app
```

### Frontend

Start dev server:

```bash
cd frontend
npm run dev
```

Build:

```bash
cd frontend
npm run build
```

Lint:

```bash
cd frontend
npm run lint
```

## Environment Variables

Important backend variables:

- `DATABASE_URL`: primary database connection. If absent, SQLite is used.
- `READONLY_DATABASE_URL`: read-only connection for chat SQL queries. Falls back to `DATABASE_URL`.
- `GEMINI_API_KEY`: enables Gemini OCR and the LangGraph/Gemini chat agent.
- `GCS_BUCKET_NAME`: enables receipt image upload to Google Cloud Storage.
- `DEV_USER_EMAIL`: local-development user identity when IAP headers are absent.

## Editing Guidance

### If you are changing backend API behavior

- Check `frontend/src/App.tsx` for the exact API contract before changing request or response shapes.
- Preserve per-user isolation. New expense queries should continue to filter on `current_user.id`.
- For agent or SQL work, maintain the read-only guarantees in `backend/app/agent/tools.py`.
- Keep SQLite and PostgreSQL compatibility in mind. `backend/app/db.py` and `backend/app/agent/tools.py` already contain dialect-specific behavior.

### If you are changing agent behavior

- Prefer editing `backend/app/agent/tools.py` for data access logic and `backend/app/agent/graph.py` for tool selection/prompting.
- Do not bypass `_validate_read_only_sql` for generated SQL.
- Existing tests cover important safety properties. Extend `backend/tests/agent/test_tools.py` when modifying agent tools or SQL validation.

### If you are changing ingestion behavior

- Spreadsheet ingestion supports CSV plus Excel, including a multi-sheet monthly format like `JAN_2025`.
- OCR/image ingestion depends on Gemini and may store assets in GCS or local uploads.
- Be careful with parsing heuristics in `expenses.py`; they drive category cleanup, amount normalization, and date derivation.

### If you are changing frontend behavior

- Most UI logic is centralized in `frontend/src/App.tsx`; expect a large single-file component.
- The app assumes `/api` routes from the same origin in production and `http://localhost:8000/api` during local Vite development.
- Preserve the empty-state and demo-mode paths unless intentionally changing onboarding behavior.

## Testing Expectations

- At minimum, run targeted backend tests when changing agent logic or SQL behavior:

```bash
cd backend
uv run pytest backend/tests/agent/test_tools.py
```

- Run `npm run build` after frontend changes.
- There is current backend test coverage for agent tool behavior; there does not appear to be meaningful frontend automated test coverage yet.

## Known Repo-Specific Notes

- `.agents/hooks.json` defines local hooks for secret checking, commit validation, and Python post-edit checks. The referenced script paths should be treated carefully because they appear environment-specific.
- `backend/.venv`, `frontend/node_modules`, and `frontend/dist` are present in the workspace. Avoid making assumptions based on generated/vendor content unless the task explicitly requires it.
- `README.md` describes the intended production architecture, but agent changes should be grounded in the live code paths above.

## Preferred Workflow For Future Agents

1. Inspect the relevant backend or frontend entrypoint before editing.
2. Confirm the user-facing contract in both the API and the UI when touching endpoints.
3. Make the smallest coherent change.
4. Run the narrowest useful verification first, then broader checks if the change is cross-cutting.
5. Call out any unverified risk, especially around SQL safety, auth scoping, and SQLite/PostgreSQL differences.
