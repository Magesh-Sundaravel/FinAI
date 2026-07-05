# Finance AI Agents 🪙🤖

A modern, high-performance monorepo application designed to automate, parse, and analyze years of personal expenses using intelligent agents. Built with a FastAPI backend and a React (TypeScript) + Vite frontend.

## 🛠️ Technology Stack

- **Backend**: FastAPI, Python 3.12+, managed via **`uv`** (extremely fast package resolver & environment manager) and Pandas/OpenPyXL for spreadsheet ingestion.
- **Frontend**: React (TypeScript), Vite.js, Vanilla CSS styling (premium dark-theme, custom glassmorphism components), and Lucide React Icons.
- **AI Core**: Heuristic keyword analyzer with optional integration with the **Gemini 2.5 Flash** API for advanced budget reasoning and trends analysis.

---

## 📁 Repository Structure

```text
FinAI/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/
│   │   │   │   ├── agent.py      # AI Agent reasoning routes
│   │   │   │   └── expenses.py   # Spreadsheet parser & ledger endpoints
│   │   └── main.py           # API server entrypoint & CORS setup
│   ├── pyproject.toml        # uv python dependencies configuration
│   └── README.md
├── frontend/                 # React + Vite Client
│   ├── src/
│   │   ├── App.tsx           # React Dashboard interface logic & SVG Charts
│   │   └── index.css         # UI Styling system
│   ├── package.json          # Node dependencies
│   └── README.md
├── .gitignore                # Root gitignore rules
└── README.md                 # Project guide (this file)
```

---

## 🚀 Getting Started

### 1. Prerequisite Checklist
Make sure you have the following installed:
- Git
- Python 3.12+ (or run `uv python install 3.12` to let uv manage it)
- [uv](https://github.com/astral-sh/uv) (Python package installer)
- Node.js (v20+ recommended) & npm

---

### 2. Launching the Backend API
1. Navigate into the backend directory:
   ```bash
   cd backend
   ```
2. *(Optional)* If you'd like to enable full LLM conversational analysis, export your Gemini API key:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```
3. Start the FastAPI server (uv will automatically create a virtual environment, sync packages, and run the server):
   ```bash
   uv run uvicorn app.main:app --port 8000 --reload
   ```
   - The API will be active at: `http://localhost:8000`
   - Interactive Swagger API docs: `http://localhost:8000/docs`

---

### 3. Launching the Frontend App
1. Open a new terminal window and navigate into the frontend folder:
   ```bash
   cd frontend
   ```
2. Install the node packages:
   ```bash
   npm install
   ```
3. Run the hot-reloading development server:
   ```bash
   npm run dev
   ```
   - Open your browser to the local URL displayed (typically `http://localhost:5173`).

---

## ✨ Features Checklist
1. **Spreadsheet Ingest System**: Drag & drop your `.csv`, `.xlsx`, or `.xls` expense sheets. The backend parses data using Pandas, auto-detects fields representing dates, vendor descriptions, category labels, and amounts, then saves it to a persistent local ledger.
2. **Interactive Ledger**: Search, filter by category, clear database files, or add manual transactions via the UI modal.
3. **Advanced SVG Dashboard**: Zero-dependency, responsive, and custom-styled SVG bar charts and category spending progress sheets.
4. **Finance AI Agent Chat**: Talk directly to your financial advisor bot. Ask questions like:
   - *"How much did I spend in total?"*
   - *"Show spending by category"*
   - *"What is my highest expense?"*
   - *"Show me expenses related to Amazon"*
