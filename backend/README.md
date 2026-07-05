# Finance AI Agents - FastAPI Backend 🐍

This is the backend API for the FinAI platform. It exposes endpoints to parse expense spreadsheets, query aggregated statistics, and chat with a financial analyzer agent.

## 🚀 Getting Started

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

1. **Install dependencies and start local dev server**:
   ```bash
   uv run uvicorn app.main:app --port 8000 --reload
   ```

2. **Run with Gemini API Enabled**:
   To enable advanced conversational analysis and financial forecasting, export your Gemini API key:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   uv run uvicorn app.main:app --port 8000 --reload
   ```

## 📡 API Endpoints Summary

- `GET /` - Base API status.
- `GET /api/health` - API health check.
- `GET /api/expenses/` - Fetch all tracked expenses.
- `POST /api/expenses/` - Track a single manual expense.
- `POST /api/expenses/upload` - Upload Excel/CSV spreadsheet statement.
- `GET /api/expenses/summary` - Aggregated month and category metrics.
- `DELETE /api/expenses/clear` - Delete all loaded ledger data.
- `POST /api/agent/chat` - Interact with the Finance AI Agent.

Interactive Swagger API docs are available at `http://localhost:8000/docs`.
