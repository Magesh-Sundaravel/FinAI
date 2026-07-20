# Finance AI Agents 🪙🤖

A professional, high-performance monorepo application designed to automate parsing, categorizing, and analyzing personal expenses using intelligent agents. Built with a **FastAPI backend** and a **React (TypeScript) + Vite frontend**, the application is fully optimized for production deployment on **Google Cloud Run** and **Google Cloud SQL (PostgreSQL)**.

---

## ✨ Core Features

* 📊 **Multi-Year Expense Ledger**: Drag & drop `.csv`, `.xlsx`, or `.xls` bank/credit card statements. The system automatically maps column fields, parses transactions, and normalizes categories.
* 📷 **AI Ingestion (Gemini OCR)**: Upload a receipt or utility bill image. The system streams the file to Google Cloud Storage (GCS) and invokes the Gemini 2.5 Flash Vision API to extract descriptions, categories, amounts, dates, and seasonal tags.
* 💬 **Secured Text-to-SQL Chatbot**: Query your database in natural language (e.g. *"Show my groceries spending last winter"*). The backend translates the text to PostgreSQL-compatible SQL using Gemini and executes it.
* 🛡️ **Dual-Database Security**: Chatbot queries run under a restricted, read-only database session to prevent SQL injection or destructive operations (`DROP`, `DELETE`, etc.), while the primary application runs under a standard read-write owner role.
* 🎨 **Premium Dark-Theme Dashboard**: Zero-dependency, responsive SVG charts, glassmorphism UI components, and smooth animations.

---

## 🏛️ Production Architecture

```mermaid
graph TD
    Client[Web Browser / React Client] -- "HTTPS (port 8080)" --> CloudRun[Google Cloud Run FastAPI Container]
    
    subgraph FastAPI Container
        Static[FastAPI Static Files Middleware]
        API[FastAPI Endpoints /api]
    end
    
    API -- "SELECT Queries (Read-Only User)" --> ReadOnlyDB[(Cloud SQL Postgres - Read-Only Role)]
    API -- "Migrations & Writes (Owner User)" --> OwnerDB[(Cloud SQL Postgres - Owner Role)]
    API -- "Extract Text" --> Gemini[Gemini 2.5 Flash API]
    API -- "Upload Bill/Receipt Image" --> GCS["Google Cloud Storage Bucket (gs://finai-receipts)"]

    Client -- "Direct HTTPS Media Load" --> GCS
```

---

## 📁 Repository Structure

```text
FinAI/
├── .github/workflows/        # CI/CD Pipeline Configuration
│   └── deploy.yml            # Google Cloud Run deployment workflow
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/endpoints/
│   │   │   ├── agent.py      # AI Agent & Text-to-SQL endpoints
│   │   │   └── expenses.py   # OCR ingestion, ledger parsing & CRUD
│   │   ├── main.py           # API server entrypoint & CORS setup
│   │   ├── db.py             # Database engine & session declarations
│   │   └── models.py         # SQLAlchemy / SQLModel schema tables
│   ├── pyproject.toml        # uv python dependencies configuration
│   └── Dockerfile            # Multi-stage production container configuration
└── frontend/                 # React + Vite Client
    ├── src/
    │   ├── App.tsx           # React Dashboard interface logic & SVG Charts
    │   └── index.css         # UI Styling system
    └── package.json          # Node dependencies
```

---

## 🚀 Getting Started

### 1. Local Development Sandbox (SQLite)
FastAPI defaults to a local SQLite database when no external database URL is configured.

#### Local Setup
Use one explicit local identity end-to-end. Set `DEV_USER_EMAIL` once, seed data for that same email, and run the backend in the same shell so the profile, expenses, and summaries all resolve to the same user.

```bash
cd backend
export DEV_USER_EMAIL="your-email@example.com"
uv run python scripts/seed_local_data.py --reset
uv run uvicorn app.main:app --port 8000 --reload
```

Ensure you have [uv](https://github.com/astral-sh/uv) installed. If `GEMINI_API_KEY` is already present in `backend/.env`, you do not need to export it again. Only export it in the shell if you want to override the `.env` value for the current session.

If `DEV_USER_EMAIL` is not set and no Google IAP header is present, the backend now returns `401 Unauthorized` instead of silently falling back to a hard-coded local user. This avoids seeding data for one email and then accidentally browsing the app as a different user.

#### Backend
Interactive docs will be active at: `http://localhost:8000/docs`.

The `/api/expenses/profile` response also reports the current auth source so the UI can clearly distinguish between:

* `google_iap`: production-style authenticated user from Google IAP
* `local_dev_env`: explicit local development user from `DEV_USER_EMAIL`
* `demo_mode`: frontend fallback when the backend is unreachable

#### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. The client automatically hooks into `http://localhost:8000/api`.

---

## 📦 Production Deployment (Google Cloud Run)

The production configuration uses a unified Docker container serving both React built assets and the FastAPI server.

### 1. Build and Run Container Locally
To test the production container locally:
```bash
docker build -t finai-app -f backend/Dockerfile .
docker run -p 8080:8080 \
  -e DATABASE_URL="postgresql://user:password@localhost:5432/dbname" \
  -e GEMINI_API_KEY="your-api-key" \
  finai-app
```

### 2. CI/CD Deployment
Our [.github/workflows/deploy.yml](.github/workflows/deploy.yml) workflow automatically deploys to Google Cloud Run when commits are pushed to the `main` branch or a release tag is pushed. 

Ensure the following GitHub Secrets are configured in your repository settings:
* `GCP_SA_KEY`: Service account credentials JSON.
* `GCP_PROJECT_ID`: Your GCP project ID.
* `GCP_INSTANCE_CONN_NAME`: Cloud SQL instance connection name.
* `DATABASE_URL`: Cloud SQL owner connection string.
* `READONLY_DATABASE_URL`: Cloud SQL read-only agent connection string.
* `GEMINI_API_KEY`: Google Gemini API Access Token.
* `GCS_BUCKET_NAME`: Google Cloud Storage bucket name for receipt images.

---

## 🏷️ GitHub Releases & Best Practices

To maintain a professional release lifecycle for version tags:

### 1. Create a Release Tag
Ensure your `main` branch is up to date:
```bash
git checkout main
git pull origin main
```
Tag the version and push it:
```bash
git tag -a v0.0.1 -m "Release v0.0.1: Initial production release with unified container, GCS integration, Cloud SQL Postgres migration, and dual DB connection roles."
git push origin v0.0.1
```

### 2. Drafting the Release in GitHub
Go to **Releases -> Draft a new release** on GitHub:
* Choose the tag: `v0.0.1`.
* Title: `v0.0.1 - Production Release`.
* Body description: Include highlights of the features, DB role security mechanisms, and GCS integrations.
