import json
import os
import urllib.error
import urllib.request
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agent.graph import build_agent_graph
from app.auth import get_current_user
from app.db import get_readonly_session
from app.models import Expense, User

router = APIRouter()


def _extract_text(content) -> str:
    """
    AIMessage.content is either a plain string or a list of content blocks
    (e.g. [{"type": "text", "text": "..."}]) depending on the model/provider.
    Normalize to a plain string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
        return "".join(parts)
    return str(content)


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    suggested_actions: Optional[List[str]] = None


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
async def chat_with_agent(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_readonly_session)
):
    api_key = os.environ.get("GEMINI_API_KEY")

    if api_key:
        graph = build_agent_graph()
        thread_id = req.thread_id or str(current_user.id)
        config = {"configurable": {"thread_id": thread_id, "user_id": str(current_user.id)}}

        try:
            result = await graph.ainvoke({"messages": [("user", req.message)]}, config)
            last_message = result["messages"][-1]
            response_text = _extract_text(last_message.content) or "I retrieved the data but couldn't generate a description."
        except Exception as e:
            # Fallback to local rule-based agent if the agent loop fails
            statement = select(Expense).where(Expense.user_id == current_user.id).order_by(Expense.date.desc())
            result_rows = await session.exec(statement)
            expenses = result_rows.all()
            response_text = f"An error occurred while communicating with the AI model: {str(e)}. Falling back to local helper.\n\n" + run_local_rule_based_agent(req.message, expenses)
    else:
        # Fallback to local rule-based analysis
        statement = select(Expense).where(Expense.user_id == current_user.id).order_by(Expense.date.desc())
        result_rows = await session.exec(statement)
        expenses = result_rows.all()
        response_text = run_local_rule_based_agent(req.message, expenses)

    # Standard suggested actions
    actions = [
        "How much did I spend in total?",
        "What is my highest expense?",
        "Show my spending by category",
        "Clear all expense data",
    ]

    return ChatResponse(response=response_text, suggested_actions=actions)
