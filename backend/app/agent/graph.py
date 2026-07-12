"""
LangGraph ReAct loop for the expense-tracking agent.

This module is the only place that depends on LangChain/LangGraph. It adapts
the framework-agnostic functions in app/agent/tools.py into LangChain tools,
threading the per-request user_id through RunnableConfig (config["configurable"])
rather than baking it into the graph, so the compiled graph and its
MemorySaver checkpointer can be built once and reused across users/requests.
"""
import os

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent import tools as core_tools
from app.agent.state import AgentState

SYSTEM_PROMPT = """You are "Finance AI Agent", a personal expense-tracking assistant.

You have four tools:
- get_schema_info: inspect the expenses table columns/categories.
- query_transactions: look up individual transactions (a single purchase, a
  specific receipt, "the most expensive thing I bought", "show me my last 5
  purchases at X"). Returns raw rows.
- query_category_totals: aggregate spend totals by category, month, or
  season ("how much did I spend on groceries", "spending by month"). Returns
  summed amounts, never individual transactions.
- query_expenses_sql: fallback for analytical questions that don't fit the
  two tools above.

CRITICAL — disambiguation: many questions are genuinely ambiguous between a
single transaction and a category total. For example "what's the most
expensive thing I owned/bought" could mean either the single largest
transaction (query_transactions) or the category with the highest total
spend (query_category_totals). When a question could reasonably mean either,
do NOT guess and do NOT call a tool — respond directly asking the user which
they mean, briefly explaining the two interpretations. Only call a tool once
the intent is clear from the question or from the user's clarification.

Give concise, friendly, markdown-formatted answers grounded only in tool
results. Never fabricate numbers.
"""


@tool
async def get_schema_info() -> str:
    """Return the expenses table schema (columns and their meaning)."""
    return await core_tools.get_schema_info()


@tool
async def query_transactions(
    description_contains: str | None = None,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    order_by: str = "date",
    order_direction: str = "desc",
    limit: int = 10,
    *,
    config: RunnableConfig,
) -> str:
    """Look up individual, line-item transactions (single purchases/receipts).

    Use this — not query_category_totals — for anything about a SPECIFIC
    transaction or a small list of them: the single largest/most expensive
    purchase, "what did I buy at X", the last N transactions, a particular
    receipt. It returns raw rows, not aggregated totals.

    order_by must be "amount" or "date"; order_direction must be "asc" or "desc".
    """
    user_id = config["configurable"]["user_id"]
    return await core_tools.query_transactions(
        user_id=user_id,
        description_contains=description_contains,
        category=category,
        date_from=date_from,
        date_to=date_to,
        order_by=order_by,  # type: ignore[arg-type]
        order_direction=order_direction,  # type: ignore[arg-type]
        limit=limit,
    )


@tool
async def query_category_totals(
    group_by: str = "category",
    date_from: str | None = None,
    date_to: str | None = None,
    *,
    config: RunnableConfig,
) -> str:
    """Aggregate spending totals grouped by category, month, or season.

    Use this — not query_transactions — for questions about how much was
    spent IN TOTAL on something: totals per category, monthly spend trends,
    seasonal breakdowns. It returns summed amounts, never individual
    transactions.

    group_by must be one of "category", "month", or "season".
    """
    user_id = config["configurable"]["user_id"]
    return await core_tools.query_category_totals(
        user_id=user_id,
        group_by=group_by,  # type: ignore[arg-type]
        date_from=date_from,
        date_to=date_to,
    )


@tool
async def query_expenses_sql(natural_language_query: str, *, config: RunnableConfig) -> str:
    """Fallback for analytical questions that don't fit query_transactions or
    query_category_totals (e.g. multi-condition filters, comparisons across
    time periods). Generates and runs a read-only SQL SELECT against the
    expenses table for this user. Prefer the more specific tools when they apply.
    """
    user_id = config["configurable"]["user_id"]
    return await core_tools.query_expenses_sql(natural_language_query, user_id=user_id)


TOOLS = [get_schema_info, query_transactions, query_category_totals, query_expenses_sql]

_checkpointer = MemorySaver()
_compiled_graph = None
_llm_with_tools = None


def _get_llm():
    global _llm_with_tools
    if _llm_with_tools is None:
        _llm_with_tools = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=os.environ.get("GEMINI_API_KEY"),
        ).bind_tools(TOOLS)
    return _llm_with_tools


async def _agent_node(state: AgentState) -> dict:
    llm = _get_llm()
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


def build_agent_graph():
    """
    Build (once) and return the compiled StateGraph: agent -> tools -> agent,
    looping until the LLM returns a response with no tool_calls. A MemorySaver
    checkpointer keyed by thread_id gives multi-turn memory across chat turns.
    """
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    builder = StateGraph(AgentState)
    builder.add_node("agent", _agent_node)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")

    _compiled_graph = builder.compile(checkpointer=_checkpointer)
    return _compiled_graph
