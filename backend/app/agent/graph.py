from functools import lru_cache

import groq
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.tools import TOOLS
from app.config import get_settings

# Guards against tool-call loops; a voice turn should never need more than a few hops.
RECURSION_LIMIT = 10


def build_llm() -> BaseChatModel:
    settings = get_settings()
    kwargs = {}
    if "gpt-oss" in settings.groq_model:
        # Trades answer quality against time-to-first-token on voice turns.
        kwargs["reasoning_effort"] = settings.groq_reasoning_effort
    return ChatGroq(
        model=settings.groq_model,
        # A placeholder keeps startup working without a key; calls then fail and the runner
        # speaks a graceful apology instead of the endpoint returning a 500 mid-call.
        api_key=settings.groq_api_key or "missing-groq-api-key",
        temperature=settings.groq_temperature,
        max_tokens=400,
        streaming=True,
        **kwargs,
    )


def _after_tools(state: MessagesState) -> str:
    """Stop once the agent hangs up; otherwise let it read the tool results and reply."""
    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break
        if message.name == "end_call":
            return END
    return "agent"


def build_graph(llm: BaseChatModel | None = None) -> CompiledStateGraph:
    # gpt-oss on Groq occasionally emits malformed tool-call JSON; one retry usually succeeds.
    model = (
        (llm or build_llm())
        .bind_tools(TOOLS)
        .with_retry(retry_if_exception_type=(groq.APIError,), stop_after_attempt=2)
    )

    async def agent(state: MessagesState, config: RunnableConfig) -> dict:
        response = await model.ainvoke(state["messages"], config)
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_conditional_edges("tools", _after_tools, ["agent", END])
    return graph.compile()


@lru_cache
def get_graph() -> CompiledStateGraph:
    return build_graph()
