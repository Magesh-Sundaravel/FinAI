# 📋 Project Specification: FinAI (FinanceAI)

This specification outlines the architecture, data models, and features for **FinAI**, a system designed to consolidate 6 years of historical spreadsheet expenses and automate ongoing tracking via receipt/bill OCR and an interactive AI financial assistant.

---

## 🎯 Project Goals
1. **Spreadsheet Ingestion**: Clean, parse, and load 6 years of spreadsheet-based history into a structured relational database.
2. **Receipt Ingestion Automation**: Take a photo of a bill or grocery receipt, upload it, extract line items (names, quantities, prices) using Gemini Vision API, and store them in the database.
3. **Structured Storage**: Migrate data to **PostgreSQL** to support rich analytics and relational queries.
4. **Rich Analytics Frontend**: Clean dashboard displaying spending trends across **Home (Overview)**, **Monthly**, and **Yearly** views.
5. **Conversational Financial Chatbot**: Chat with an LLM agent that executes secure SQL queries or queries the database to answer natural language questions about personal expenses.

---

## 🛠️ Technology Stack

- **Backend**:
  - **FastAPI** (Python 3.12, managed with `uv`)
  - **SQLAlchemy** / **SQLModel** (ORM for PostgreSQL database integration)
  - **Google GenAI SDK** (Gemini 2.5 Flash for Receipt Vision OCR and SQL Query Generation)
  - **Pandas** (Data cleaning during initial spreadsheet imports)
- **Database**:
  - **PostgreSQL** (relational database to track transactions and line items)
- **Frontend**:
  - **React (TypeScript)** + **Vite.js**
  - **Lucide Icons**
  - Custom Vanilla CSS styling (premium dark-theme, charts, and interactive chat interface)

---

## 🗄️ Database Schema (PostgreSQL)

To keep the system fast and straightforward, we will use a single flat table to track expenses. The primary currency is Euros (€), and it includes a `season` attribute for temporal analysis.

### 1. `expenses`
Represents a single expense item or utility bill.
- `id` (UUID, Primary Key)
- `date` (Date) - Transaction or bill statement date
- `season` (VARCHAR) - Derived season: "Winter" (Dec-Feb), "Spring" (Mar-May), "Summer" (Jun-Aug), "Autumn" (Sep-Nov)
- `description` (VARCHAR) - Merchant, vendor, or utility provider (e.g., "Enel", "Fastweb", "Esselunga", "Conad")
- `category` (VARCHAR) - Category of spend (e.g., "Rent", "WiFi", "Electricity", "Gas", "Groceries", "Public Transit", "Gelato/Dining Out", "Travel")
- `amount` (DECIMAL) - Expense cost in Euros (€)
- `bill_image_url` (VARCHAR, Optional) - Filepath to the uploaded receipt/bill photo
- `created_at` (Timestamp)

---

## ⚙️ Core Architecture & Features

### 1. Spreadsheet Data Migrator
- Ingests the 6 years of historical spreadsheet data (`.csv` or `.xlsx`).
- Standardizes categories (WiFi, Gas, Electricity, Groceries, etc.), assigns the correct `season` based on the date, converts the amounts to Euros, and loads the data into PostgreSQL.

### 2. Automated Bill/Receipt Ingestion (OCR)
- Upload receipt or utility bill image via the React UI.
- Backend sends the image to the Gemini 2.5 Flash API with a prompt to return a structured JSON object: description, category (Auto-detected, e.g. "Electricity" for Enel bills), amount, and date.
- The backend automatically calculates the `season` from the date and saves the flat record to the database.

### 3. Frontend Views (React Client)
- **Home (Overview)**: Summary metrics (total spent, average monthly costs, recent bills/receipts).
- **Monthly**: Monthly aggregates, category distributions, utilities tracking (WiFi vs. Gas vs. Electricity).
- **Yearly**: Seasonal spending distribution comparison (e.g., heating utility spikes in Winter vs. vacation spending in Summer).
- **Chatbot Section**: A terminal/chat bubble panel linked to the backend AI agent.

### 4. Natural Language Chatbot
- The user can ask questions in natural language:
  - *"How much was my electricity bill last winter?"*
  - *"List my expenses for gas in 2025."*
  - *"What did I spend on transit during summer?"*
- The backend gives Gemini the database schema and asks it to generate a safe SQL query matching the query.
- The backend runs the query against the `expenses` table and hands the results back to Gemini to output a simple, markdown-styled response.

---

## 🗺️ Phased Implementation Plan

1. **Phase 1: Database & Spreadsheet Migration**
   - Spin up PostgreSQL instance.
   - Implement data migration scripts to import historical student spreadsheets (mapping dates to seasons, cleaning categories).
   - Update backend routes to read/write expenses to PostgreSQL.

2. **Phase 2: Receipt & Bill OCR Integration**
   - Setup upload endpoints to accept bill images.
   - Write backend integration to call Gemini Vision API.
   - Verify parsing of bills (WiFi, electricity, gas, groceries) into standard schema fields.

3. **Phase 3: Conversational Database Agent**
   - Build backend agent loop (Text-to-SQL for the flat `expenses` table).
   - Establish safe constraints (read-only execution context) for SQL queries.

4. **Phase 4: Responsive Frontend Enhancement**
   - Refactor frontend tabs into Home, Monthly, Yearly, and Chatbot sections.
   - Add support for uploading images with automated category confirmations.
