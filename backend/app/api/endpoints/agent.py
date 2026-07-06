import os
import json
import re
import urllib.request
import urllib.error
from typing import Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import Session
from google import genai
from google.genai import types
from app.db import engine, get_session
from app.api.endpoints.expenses import load_expenses
from app.models import Expense

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None


class ChatResponse(BaseModel):
    response: str
    suggested_actions: Optional[List[str]] = None


class AgentDecision(BaseModel):
    requires_db: bool = Field(description="Set to true if the user query asks for specific expense data, summaries, calculations, or trends from their database. Set to false for general conversational questions, greetings, or actions like clearing data.")
    sql_query: Optional[str] = Field(default=None, description="The SQL query to execute if requires_db is true. Must start with SELECT and be read-only.")
    explanation: Optional[str] = Field(default=None, description="Provide a conversational response here if requires_db is false.")


def execute_read_only_query(query_str: str, session: Session) -> list:
    """
    Safely execute a generated SQL query ensuring it is read-only.
    """
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate", "replace", "create"]
    query_lower = query_str.lower()
    for word in forbidden:
        if re.search(r'\b' + word + r'\b', query_lower):
            raise ValueError(f"Security policy violation: query contains forbidden keyword '{word}'")
            
    if not query_lower.strip().startswith("select"):
        raise ValueError("Security policy violation: only SELECT queries are allowed")
        
    if "limit" not in query_lower:
        query_str = query_str.strip().rstrip(';')
        query_str = f"{query_str} LIMIT 100"
        
    result = session.execute(text(query_str))
    return [dict(row._mapping) for row in result.all()]


def get_gemini_response(prompt: str, api_key: str) -> str:
    """
    Call Gemini API using urllib to avoid heavy external dependencies.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        req = urllib.request.Request(
            url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        try:
            err_json = json.loads(error_msg)
            return f"Gemini API Error: {err_json['error']['message']}"
        except Exception:
            return f"Gemini API Error (HTTP {e.code}): {error_msg}"
    except Exception as e:
        return f"Failed to connect to Gemini API: {str(e)}"


def run_local_rule_based_agent(message: str, expenses) -> str:
    """
    Analyze loaded expenses using local heuristic logic for instant out-of-the-box answers.
    """
    msg_lower = message.lower()

    if not expenses:
        return (
            "Hi there! I'm your Finance AI Agent. I see that you don't have any expenses loaded yet. "
            "Please upload your expense spreadsheet (Excel or CSV) using the 'Upload' tab above, "
            "and I will help you analyze, summarize, and answer questions about your spending!"
        )

    total_spent = sum(e.amount for e in expenses)
    categories = list(set(e.category for e in expenses))
    num_tx = len(expenses)

    # 1. Ask about total spending
    if any(
        k in msg_lower
        for k in ["total", "how much did i spend", "overall spend", "summary"]
    ):
        # Check if they specified a category
        for cat in categories:
            if cat.lower() in msg_lower:
                cat_spent = sum(
                    e.amount for e in expenses if e.category.lower() == cat.lower()
                )
                cat_tx = len([e for e in expenses if e.category.lower() == cat.lower()])
                return (
                    f"You spent a total of **€{cat_spent:,.2f}** on **{cat}** across {cat_tx} transaction(s). "
                    f"This accounts for {((cat_spent / total_spent) * 100):.1f}% of your total spending (€{total_spent:,.2f})."
                )
        return (
            f"You have tracked a total of **€{total_spent:,.2f}** across **{num_tx}** transactions. "
            f"Your spending is spread across {len(categories)} categories: {', '.join(categories)}."
        )

    # 2. Ask about categories
    if any(k in msg_lower for k in ["categories", "category", "tags"]):
        cat_summaries = []
        for cat in categories:
            cat_spent = sum(
                e.amount for e in expenses if e.category.lower() == cat.lower()
            )
            cat_summaries.append(f"- **{cat}**: €{cat_spent:,.2f}")
        cat_text = "\n".join(cat_summaries)
        return (
            f"You have expenses in **{len(categories)}** categories:\n\n{cat_text}\n\n"
            f"The total spending is **€{total_spent:,.2f}**."
        )

    # 3. Ask about highest expense
    if any(
        k in msg_lower for k in ["highest", "max", "expensive", "largest", "biggest"]
    ):
        highest = max(expenses, key=lambda x: x.amount)
        return (
            f"Your single highest expense was **€{highest.amount:,.2f}** on **{highest.date}** "
            f"for **'{highest.description}'** (Category: {highest.category})."
        )

    # 4. Search for a specific merchant/description
    found_tx: List[Expense] = []
    for e in expenses:
        if e.description.lower() in msg_lower or msg_lower in e.description.lower():
            # Avoid too long lists
            if len(found_tx) < 5:
                found_tx.append(e)
            else:
                # keep count
                found_tx.append(e)

    if len(found_tx) > 0:
        total_found = sum(e.amount for e in found_tx)
        tx_list_str = "\n".join(
            [
                f"- {e.date}: **{e.description}** - €{e.amount:,.2f} ({e.category})"
                for e in found_tx[:5]
            ]
        )
        more_str = (
            f"\n- *and {len(found_tx) - 5} more transactions...*"
            if len(found_tx) > 5
            else ""
        )
        return (
            f"I found {len(found_tx)} transaction(s) matching your search:\n\n{tx_list_str}{more_str}\n\n"
            f"Total spent on these transactions: **€{total_found:,.2f}**."
        )

    # 5. Default greeting / general explanation
    return (
        f"I'm your Finance AI Agent! I currently have **{num_tx}** transactions loaded totaling **€{total_spent:,.2f}**.\n\n"
        f"Since the `GEMINI_API_KEY` is not set, I am running in local analysis mode. You can ask me questions like:\n"
        f"- *'How much did I spend in total?'*\n"
        f"- *'What are my spending categories?'*\n"
        f"- *'What was my highest expense?'*\n"
        f"- *'Show me expenses related to [merchant name]'*\n\n"
        f"To enable advanced AI reasoning (e.g. forecasting, custom categorization, budget planning), configure the `GEMINI_API_KEY` in the backend environment."
    )


@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(
    req: ChatRequest,
    session: Session = Depends(get_session)
):
    api_key = os.environ.get("GEMINI_API_KEY")

    if api_key:
        client = genai.Client(api_key=api_key)
        dialect_name = engine.dialect.name
        
        prompt = f"""
You are a decision and SQL generation assistant for a personal finance chatbot.
Your task is to analyze the user's question, determine if it requires database querying, and if so, generate a read-only SQL query for the user's question using the 'expenses' table.

Database Table: expenses
Schema:
- id: UUID (Primary Key)
- date: DATE (The date of the transaction/expense, format: YYYY-MM-DD)
- season: VARCHAR (Derived season: 'Winter', 'Spring', 'Summer', 'Autumn')
- description: VARCHAR (The merchant or vendor name)
- category: VARCHAR (The category of spend, e.g. 'Rent', 'WiFi', 'Electricity', 'Gas', 'Groceries', 'Travel & Transit', 'Gelato/Dining Out')
- amount: FLOAT (The transaction amount in Euros)
- bill_image_url: VARCHAR (Optional filepath to receipt/bill photo)
- created_at: TIMESTAMP

Guidelines:
1. Determine if the query asks for database data/calculation/aggregation (requires_db = true).
2. If requires_db is true, generate a valid SQL query starting with SELECT. Do not perform any modifications (INSERT, UPDATE, DELETE, etc.).
3. The query MUST be compatible with the database dialect: '{dialect_name}'.
   - For filtering by year/month:
     - On SQLite, use: strftime('%Y', date) = '2025' or strftime('%Y-%m', date) = '2025-01'.
     - On PostgreSQL, use: EXTRACT(YEAR FROM date) = 2025 or TO_CHAR(date, 'YYYY-MM') = '2025-01'.
   - For string search, do case-insensitive search if possible, e.g. lower(description) LIKE '%amazon%' or lower(category) = 'groceries'.
4. Do not expose internal fields like bill_image_url unless the user asks for the image/receipt of a transaction.
5. If requires_db is false, write a friendly conversational response in explanation (e.g. for greetings or non-data questions).

User Question: {req.message}
"""
        
        try:
            # Step 1: intent detection & SQL generation
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AgentDecision
                )
            )
            
            text_out = response.text
            if not text_out:
                raise ValueError("Empty response received from Gemini model.")
            decision = json.loads(text_out)
            
            if decision.get("requires_db"):
                sql_query = decision.get("sql_query")
                try:
                    # Step 2: Query execution
                    db_results = execute_read_only_query(sql_query, session)
                except Exception as db_err:
                    db_results = [{"error": str(db_err)}]
                    
                # Step 3: Synthesis
                synthesis_prompt = f"""
You are "Finance AI Agent", a professional financial analysis agent.
The user asked: "{req.message}"

To answer this question, we ran the following SQL query:
`{sql_query}`

And retrieved the following results from the database:
{json.dumps(db_results, indent=2, default=str)}

Synthesize these database results into a concise, friendly, and helpful conversational answer. Format your response with clean markdown.
If the query execution returned an error (e.g. key "error" in results), explain the problem politely and offer help.
If the results are empty, politely explain that no transactions matched their criteria.
"""
                synthesis_response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=synthesis_prompt
                )
                response_text = synthesis_response.text or "I retrieved the data but couldn't generate a description."
            else:
                response_text = decision.get("explanation") or "Hello! I am your Finance AI Agent. How can I help you today?"
                
        except Exception as e:
            # Fallback to local rule-based agent if any Gemini call fails
            response_text = f"An error occurred while communicating with the AI model: {str(e)}. Falling back to local helper.\n\n" + run_local_rule_based_agent(req.message, load_expenses())
    else:
        # Fallback to local rule-based analysis
        expenses = load_expenses()
        response_text = run_local_rule_based_agent(req.message, expenses)

    # Standard suggested actions
    actions = [
        "How much did I spend in total?",
        "What is my highest expense?",
        "Show my spending by category",
        "Clear all expense data",
    ]

    return ChatResponse(response=response_text, suggested_actions=actions)
