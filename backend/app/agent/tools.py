"""
Framework-agnostic tool logic for the expense-tracking agent.

Every function here is a plain async function with explicit parameters and no
LangChain/LangGraph imports. app/agent/graph.py adapts these into LangGraph
tools (binding the caller's user_id via RunnableConfig); the same functions
can later be registered as-is on a FastMCP server without any rewrite.
"""
import json
import os
import re
import uuid
from typing import Literal, Optional

from google import genai
from sqlmodel import text

from app.db import AsyncReadonlySessionLocal, readonly_engine

SCHEMA_INFO = """Database Table: expenses
Columns:
- id: UUID (Primary Key)
- date: DATE (the transaction date, format: YYYY-MM-DD)
- season: VARCHAR ('Winter', 'Spring', 'Summer', 'Autumn')
- description: VARCHAR (merchant or vendor name)
- category: VARCHAR (e.g. 'Rent', 'WiFi', 'Electricity', 'Gas', 'Groceries', \
'Travel & Transit', 'Gelato/Dining Out')
- amount: FLOAT (transaction amount in Euros)
- user_id: UUID (owner of the row; every query must filter on this)
- created_at: TIMESTAMP

Every query MUST be scoped to a single user_id. Do not expose bill_image_url \
or user_id in results unless explicitly asked for."""


async def get_schema_info() -> str:
    """
    Return the expenses table schema (columns and their meaning).

    Call this first if you are unsure what columns/categories are available
    before writing a custom query with query_expenses_sql.
    """
    return SCHEMA_INFO


def _user_id_param(user_id: str, dialect_name: str) -> str:
    """
    SQLite stores UUID columns as 32-char hex (no dashes); Postgres stores the
    canonical hyphenated form. Normalize the bound parameter to match.
    """
    parsed = uuid.UUID(user_id)
    return parsed.hex if dialect_name == "sqlite" else str(parsed)


async def _run_query(sql: str, params: dict) -> list[dict]:
    async with AsyncReadonlySessionLocal() as session:
        result = await session.exec(text(sql), params=params)
        return [dict(row._mapping) for row in result.all()]


async def query_transactions(
    user_id: str,
    description_contains: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    order_by: Literal["amount", "date"] = "date",
    order_direction: Literal["asc", "desc"] = "desc",
    limit: int = 10,
) -> str:
    """
    Look up individual, line-item transactions (single purchases/receipts).

    Use this — not query_category_totals — for anything about a SPECIFIC
    transaction or a small list of them: the single largest/most expensive
    purchase, "what did I buy at X", the last N transactions, a particular
    receipt. It returns raw rows, not aggregated totals.
    """
    conditions = ["user_id = :user_id"]
    params: dict = {"user_id": _user_id_param(user_id, readonly_engine.dialect.name), "limit": limit}

    if description_contains:
        conditions.append("lower(description) LIKE :description_contains")
        params["description_contains"] = f"%{description_contains.lower()}%"
    if category:
        conditions.append("lower(category) = :category")
        params["category"] = category.lower()
    if date_from:
        conditions.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("date <= :date_to")
        params["date_to"] = date_to

    order_column = "amount" if order_by == "amount" else "date"
    order_dir = "DESC" if order_direction == "desc" else "ASC"
    sql = (
        "SELECT date, description, category, amount FROM expenses "
        f"WHERE {' AND '.join(conditions)} "
        f"ORDER BY {order_column} {order_dir} LIMIT :limit"
    )

    rows = await _run_query(sql, params)
    if not rows:
        return json.dumps({"transactions": [], "message": "No matching transactions found."})
    return json.dumps({"transactions": rows}, default=str)


async def query_category_totals(
    user_id: str,
    group_by: Literal["category", "month", "season"] = "category",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> str:
    """
    Aggregate spending totals grouped by category, month, or season.

    Use this — not query_transactions — for questions about how much was
    spent IN TOTAL on something: totals per category, monthly spend trends,
    seasonal breakdowns. It returns summed amounts, never individual
    transactions.
    """
    group_column = {"category": "category", "month": "strftime('%Y-%m', date)", "season": "season"}[group_by]
    conditions = ["user_id = :user_id"]
    params: dict = {"user_id": _user_id_param(user_id, readonly_engine.dialect.name)}

    if date_from:
        conditions.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("date <= :date_to")
        params["date_to"] = date_to

    sql = (
        f"SELECT {group_column} AS group_key, SUM(amount) AS total, COUNT(*) AS transaction_count "
        "FROM expenses "
        f"WHERE {' AND '.join(conditions)} "
        f"GROUP BY {group_column} "
        "ORDER BY total DESC"
    )

    rows = await _run_query(sql, params)
    if not rows:
        return json.dumps({"totals": [], "message": "No matching expenses found."})
    return json.dumps({"totals": rows}, default=str)


def _validate_read_only_sql(sql: str, user_id: str) -> None:
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate", "replace", "create"]
    sql_lower = sql.lower()
    for word in forbidden:
        if re.search(r"\b" + word + r"\b", sql_lower):
            raise ValueError(f"Security policy violation: query contains forbidden keyword '{word}'")
    if not sql_lower.strip().startswith("select"):
        raise ValueError("Security policy violation: only SELECT queries are allowed")
    if user_id not in sql and uuid.UUID(user_id).hex not in sql:
        raise ValueError("Security policy violation: query must filter by your specific user_id")


async def query_expenses_sql(natural_language_query: str, user_id: str) -> str:
    """
    Fallback for analytical questions that don't fit query_transactions or
    query_category_totals (e.g. multi-condition filters, comparisons across
    time periods). Generates and runs a read-only SQL SELECT against the
    expenses table for this user. Prefer the more specific tools when they apply.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return json.dumps({"error": "GEMINI_API_KEY is not configured; cannot generate SQL."})

    client = genai.Client(api_key=api_key)
    dialect_name = readonly_engine.dialect.name

    prompt = f"""You generate a single read-only SQL query for the 'expenses' table.

{SCHEMA_INFO}

Guidelines:
1. The query MUST start with SELECT and must not modify data.
2. The query MUST be compatible with the '{dialect_name}' SQL dialect.
   - For filtering by year/month on SQLite: strftime('%Y', date) = '2025'.
   - For filtering by year/month on PostgreSQL: EXTRACT(YEAR FROM date) = 2025.
3. CRITICAL: every query MUST filter by user_id = '{user_id}'.
4. Return only the raw SQL, no markdown fences, no explanation.

Question: {natural_language_query}
"""
    response = await client.aio.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    sql = (response.text or "").strip().strip("`").removeprefix("sql").strip()

    try:
        _validate_read_only_sql(sql, user_id)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    query_sql = sql.strip().rstrip(";")
    if "limit" not in query_sql.lower():
        query_sql = f"{query_sql} LIMIT 100"
    if dialect_name == "sqlite":
        query_sql = query_sql.replace(user_id, uuid.UUID(user_id).hex)

    try:
        rows = await _run_query(query_sql, {})
    except Exception as e:
        return json.dumps({"error": str(e), "sql": query_sql})

    return json.dumps({"sql": query_sql, "results": rows}, default=str)
