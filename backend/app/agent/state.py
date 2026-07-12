from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """
    Conversation state for the expense-tracking ReAct agent graph.
    Extends MessagesState (a rolling, appended list of BaseMessage) so the
    agent node and ToolNode can be wired together with the prebuilt
    tools_condition edge.
    """
