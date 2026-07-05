import os
import json
import urllib.request
import urllib.error
from typing import Optional, List
from fastapi import APIRouter
from pydantic import BaseModel
from app.api.endpoints.expenses import load_expenses
from app.models import Expense

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None


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
                    f"You spent a total of **${cat_spent:,.2d}** on **{cat}** across {cat_tx} transaction(s). "
                    f"This accounts for {((cat_spent / total_spent) * 100):.1f}% of your total spending (${total_spent:,.2d})."
                )
        return (
            f"You have tracked a total of **${total_spent:,.2d}** across **{num_tx}** transactions. "
            f"Your spending is spread across {len(categories)} categories: {', '.join(categories)}."
        )

    # 2. Ask about categories
    if any(k in msg_lower for k in ["categories", "category", "tags"]):
        cat_summaries = []
        for cat in categories:
            cat_spent = sum(
                e.amount for e in expenses if e.category.lower() == cat.lower()
            )
            cat_summaries.append(f"- **{cat}**: ${cat_spent:,.2d}")
        cat_text = "\n".join(cat_summaries)
        return (
            f"You have expenses in **{len(categories)}** categories:\n\n{cat_text}\n\n"
            f"The total spending is **${total_spent:,.2d}**."
        )

    # 3. Ask about highest expense
    if any(
        k in msg_lower for k in ["highest", "max", "expensive", "largest", "biggest"]
    ):
        highest = max(expenses, key=lambda x: x.amount)
        return (
            f"Your single highest expense was **${highest.amount:,.2d}** on **{highest.date}** "
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
                f"- {e.date}: **{e.description}** - ${e.amount:,.2d} ({e.category})"
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
            f"Total spent on these transactions: **${total_found:,.2d}**."
        )

    # 5. Default greeting / general explanation
    return (
        f"I'm your Finance AI Agent! I currently have **{num_tx}** transactions loaded totaling **${total_spent:,.2d}**.\n\n"
        f"Since the `GEMINI_API_KEY` is not set, I am running in local analysis mode. You can ask me questions like:\n"
        f"- *'How much did I spend in total?'*\n"
        f"- *'What are my spending categories?'*\n"
        f"- *'What was my highest expense?'*\n"
        f"- *'Show me expenses related to [merchant name]'*\n\n"
        f"To enable advanced AI reasoning (e.g. forecasting, custom categorization, budget planning), configure the `GEMINI_API_KEY` in the backend environment."
    )


@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(req: ChatRequest):
    expenses = load_expenses()
    api_key = os.environ.get("GEMINI_API_KEY")

    if api_key:
        # Build standard financial agent prompt
        expenses_summary = ""
        if expenses:
            total_spent = sum(e.amount for e in expenses)
            # Create a simple digest of expenses to feed as context to Gemini
            # Take the latest 50 transactions to avoid overflow, plus summary
            latest_tx = sorted(expenses, key=lambda x: x.date, reverse=True)[:50]
            tx_data = [
                {
                    "date": str(e.date),
                    "description": e.description,
                    "category": e.category,
                    "amount": e.amount,
                }
                for e in latest_tx
            ]

            expenses_summary = f"""
Here is a summary of the user's expense data:
- Total Spent: ${total_spent:,.2d}
- Total Transactions: {len(expenses)}
- Categories: {list(set(e.category for e in expenses))}

Here are the latest 50 transactions:
{json.dumps(tx_data, indent=2)}
"""
        else:
            expenses_summary = "The user has not uploaded any expense data yet. Politely tell them to upload their CSV or Excel sheet."

        system_instruction = f"""
You are "Finance AI Agent", a professional financial analysis agent. 
Your goal is to help the user analyze their expense spreadsheet data, spot trends, categorize transactions, and make smart budget decisions.
Be concise, helpful, and format your output with clean markdown. 

{expenses_summary}

If the user asks questions about their expenses, calculate or analyze using the context provided. If you need data that is not in the top 50, let them know you're looking at the latest data but summarize what you can see.
"""

        prompt = f"{system_instruction}\n\nUser Query: {req.message}"
        response_text = get_gemini_response(prompt, api_key)
    else:
        # Fallback to local rule-based analysis
        response_text = run_local_rule_based_agent(req.message, expenses)

    # Standard suggested actions
    actions = [
        "How much did I spend in total?",
        "What is my highest expense?",
        "Show my spending by category",
        "Clear all expense data",
    ]

    return ChatResponse(response=response_text, suggested_actions=actions)
