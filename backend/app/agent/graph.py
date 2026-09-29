from functools import lru_cache

import groq
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_groq import ChatGroq
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.tools import TOOLS
from app.config import get_settings

# Guards against tool-call loops; a voice turn should never need more than a few hops.
RECURSION_LIMIT = 10


def build_llm(model: str | None = None, *, max_retries: int = 2) -> ChatGroq:
    settings = get_settings()
    model = model or settings.groq_model
    kwargs = {}
    if "gpt-oss" in model:
        # Trades answer quality against time-to-first-token on voice turns.
        kwargs["reasoning_effort"] = settings.groq_reasoning_effort
    return ChatGroq(
        model=model,
        # A placeholder keeps startup working without a key; calls then fail and the runner
        # speaks a graceful apology instead of the endpoint returning a 500 mid-call.
        api_key=settings.groq_api_key or "missing-groq-api-key",
        temperature=settings.groq_temperature,
        max_tokens=400,
        max_retries=max_retries,
        streaming=True,
        **kwargs,
    )


def build_model() -> Runnable:
    """The primary Groq model with tools, falling back to a second model on API errors.

    Groq rate limits are per model, so when the primary hits its tokens-per-minute limit the
    fallback usually still has headroom. Disabling SDK retries on the primary makes the switch
    immediate instead of waiting out the limit. The fallback also covers gpt-oss's occasional
    malformed tool-call JSON.
    """
    settings = get_settings()
    if not settings.groq_fallback_model:
        return build_llm().bind_tools(TOOLS)
    primary = build_llm(max_retries=0).bind_tools(TOOLS)
    fallback = build_llm(settings.groq_fallback_model).bind_tools(TOOLS)
    return primary.with_fallbacks([fallback], exceptions_to_handle=(groq.APIError,))


def _after_tools(state: MessagesState) -> str:
    """Stop once the agent hangs up; otherwise let it read the tool results and reply."""
    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break
        if message.name == "end_call":
            return END
    return "agent"


def build_graph(llm: BaseChatModel | None = None) -> CompiledStateGraph:
    model = llm.bind_tools(TOOLS) if llm else build_model()

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
