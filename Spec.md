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

To track aggregate transactions as well as itemized details (e.g., individual items from a grocery bill), we will use a two-table relational structure:

### 1. `transactions`
Represents a single purchase/receipt.
- `id` (UUID, Primary Key)
- `date` (Date)
- `description` (VARCHAR) - Merchant or vendor name (e.g., "Whole Foods")
- `category` (VARCHAR) - Main category (e.g., "Groceries", "Utilities")
- `total_amount` (DECIMAL) - Total cost of transaction
- `receipt_image_url` (VARCHAR, Optional) - Path/URL to the uploaded receipt photo
- `created_at` (Timestamp)

### 2. `transaction_items`
Represents individual items within a transaction (crucial for itemized grocery receipts).
- `id` (UUID, Primary Key)
- `transaction_id` (UUID, Foreign Key referencing `transactions.id` ON DELETE CASCADE)
- `name` (VARCHAR) - Item name (e.g., "Organic Apples")
- `quantity` (INT) - Default: 1
- `unit_price` (DECIMAL)
- `total_price` (DECIMAL) - Calculated: quantity * unit_price
- `category` (VARCHAR, Optional) - Subcategory if item level differs from transaction level

---

## ⚙️ Core Architecture & Features

### 1. Spreadsheet Data Migrator
- A utility script to ingest the 6 years of historical spreadsheet data (`.csv` or `.xlsx`).
- Cleans and standardizes categories, dates, and amounts using Pandas, maps them to the database schema, and loads them into PostgreSQL.

### 2. Automated Bill/Receipt Ingestion (OCR)
- Upload receipt image via React UI.
- Backend sends the image to the Gemini 2.5 Flash API with a structured prompt asking for a JSON response matching the database schema.
- Extracts total amount, transaction date, merchant description, and itemized lists of items.
- Saves the transaction and details to the PostgreSQL database.

### 3. Frontend Views (React Client)
- **Home (Overview)**: Summary metrics (total spent, average transaction, transaction count) and recent transactions list.
- **Monthly**: Monthly charts, spending category breakdown, month-over-month comparisons.
- **Yearly**: High-level annual trends, top categories per year, heatmaps of annual spending.
- **Chatbot Section**: Standard chat panel linked to the backend AI agent.

### 4. Natural Language Chatbot
- When the user asks: *"How much did I spend on organic apples in 2025?"*
- The backend gives Gemini the database schema and asks it to generate a safe SQL query matching the user's natural language question.
- The backend executes the SQL query against PostgreSQL, retrieves the results, and hands them back to Gemini to synthesize a friendly, structured answer.

---

## 🗺️ Phased Implementation Plan

1. **Phase 1: Database & Spreadsheet Migration**
   - Spin up PostgreSQL instance.
   - Implement data migration scripts to import historical spreadsheets.
   - Update backend routes to read/write transactions to PostgreSQL instead of in-memory JSON.

2. **Phase 2: Receipt OCR Integration**
   - Setup upload endpoints to accept images.
   - Write backend integration to call Gemini Vision API.
   - Verify structured parsing of itemized receipts.

3. **Phase 3: Conversational Database Agent**
   - Build backend agent loop (Text-to-SQL).
   - Establish safe constraints (read-only execution context) for SQL queries.

4. **Phase 4: Responsive Frontend Enhancement**
   - Refactor frontend tabs into Home, Monthly, Yearly, and Chatbot sections.
   - Integrate the receipt image upload feature with loading spinners and confirmation panels.
