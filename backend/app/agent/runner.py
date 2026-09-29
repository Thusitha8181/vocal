"""Runs one conversational turn of the LangGraph agent for an OpenAI-style chat request."""

import asyncio
import logging
import random
import re
import time
import uuid
from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import RECURSION_LIMIT
from app.agent.prompts import CallContext, render_system_prompt
from app.db.models import CallChannel
from app.services import calls

log = logging.getLogger(__name__)

# ElevenLabs keeps natural prosody when a buffer phrase ends with "... " before the real answer.
FILLERS = [
    "Sure, let me check that for you... ",
    "One moment while I look that up... ",
    "Okay, give me a second to check... ",
]
ERROR_REPLY = "Sorry, I'm having a little trouble on my side right now. Could you say that again?"
MAX_TOOL_LOG_CHARS = 4000
# Recent turns are enough context on a call and keep tokens per request (and rate limits) low.
MAX_HISTORY_MESSAGES = 12
# gpt-oss emits typographic spaces/hyphens (e.g. "500\u202fMB", "pan\u2011India").
_PLAIN_TEXT = str.maketrans({"\u202f": " ", "\u00a0": " ", "\u2011": "-", "\u2010": "-"})

_background: set[asyncio.Task[Any]] = set()


def _spawn(coro: Coroutine[Any, Any, Any]) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def wait_for_background() -> None:
    """Wait for pending turn-logging tasks (used by tests and graceful shutdown)."""
    while _background:
        await asyncio.gather(*list(_background), return_exceptions=True)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return ""


def _context_value(system_text: str, key: str) -> str | None:
    match = re.search(rf"{key}\s*[:=]\s*(\S+)", system_text)
    if not match or "{{" in match.group(1):
        return None
    value = match.group(1).strip().strip("'\"")
    return value if value.lower() not in {"", "none", "null", "undefined"} else None


@dataclass
class TurnRequest:
    conversation_id: str
    channel: CallChannel
    caller_number: str | None
    history: list[BaseMessage] = field(default_factory=list)
    # True when ElevenLabs offered its end_call system tool, so we can hand the hang-up back.
    can_end_call: bool = False


@dataclass
class EndCall:
    reason: str
    message: str


def parse_chat_request(body: dict[str, Any]) -> TurnRequest:
    """Extract call context and chat history from an OpenAI-compatible request body.

    ElevenLabs renders its own agent prompt as the system message; that prompt carries the
    conversation id and caller id via dynamic variables (see scripts/setup_elevenlabs_agent.py).
    Our real system prompt is generated server-side, so the incoming one is not forwarded.
    """
    system_text = ""
    history: list[BaseMessage] = []
    for message in body.get("messages") or []:
        role, text = message.get("role"), _content_text(message.get("content"))
        if role == "system":
            system_text += "\n" + text
        elif role == "user" and text.strip():
            history.append(HumanMessage(text))
        elif role == "assistant" and text.strip():
            history.append(AIMessage(text))

    extra = body.get("elevenlabs_extra_body") or {}
    conversation_id = (
        extra.get("conversation_id")
        or body.get("conversation_id")
        or _context_value(system_text, "conversation_id")
        or f"adhoc-{uuid.uuid4()}"
    )
    caller = extra.get("caller_id") or _context_value(system_text, "caller_id")
    offered_tools = {
        (t.get("function") or {}).get("name")
        for t in body.get("tools") or []
        if isinstance(t, dict)
    }
    return TurnRequest(
        conversation_id=str(conversation_id),
        channel=CallChannel.phone if caller else CallChannel.web,
        caller_number=caller,
        history=history,
        can_end_call="end_call" in offered_tools,
    )


async def _log_user_turn(call_id: uuid.UUID, req: TurnRequest, is_new_call: bool) -> None:
    if is_new_call and req.history and isinstance(req.history[0], AIMessage):
        await calls.add_turn(call_id, "assistant", _content_text(req.history[0].content))
    if not req.history or not isinstance(req.history[-1], HumanMessage):
        return
    text = _content_text(req.history[-1].content)
    previous = await calls.last_turn(call_id)
    if previous and previous.role == "user" and previous.content == text:
        return
    await calls.add_turn(call_id, "user", text)


async def run_turn(req: TurnRequest, graph: CompiledStateGraph) -> AsyncIterator[str | EndCall]:
    """Stream speakable text deltas for the next assistant turn, optionally ending with EndCall."""
    started = time.perf_counter()
    call, is_new_call = await calls.get_or_create_call(
        req.conversation_id, channel=req.channel, caller_number=req.caller_number
    )
    await _log_user_turn(call.id, req, is_new_call)

    customer = await calls.get_call_customer(call.id)
    system = render_system_prompt(CallContext(req.channel, req.caller_number, customer))
    config = {"configurable": {"call_id": str(call.id)}, "recursion_limit": RECURSION_LIMIT}

    spoken: list[str] = []
    first_token_ms: int | None = None
    used_filler = False
    tool_args: dict[str, dict[str, Any]] = {}
    hang_up: EndCall | None = None

    def emit(text: str) -> str:
        nonlocal first_token_ms
        text = text.translate(_PLAIN_TEXT)
        if first_token_ms is None:
            first_token_ms = int((time.perf_counter() - started) * 1000)
        spoken.append(text)
        return text

    try:
        stream = graph.astream(
            {"messages": [SystemMessage(system), *req.history[-MAX_HISTORY_MESSAGES:]]},
            config,
            stream_mode=["messages", "updates"],
        )
        async for mode, data in stream:
            if mode == "messages":
                chunk, meta = data
                if meta.get("langgraph_node") != "agent" or not isinstance(chunk, AIMessageChunk):
                    continue
                if text := _content_text(chunk.content):
                    yield emit(text)
                elif chunk.tool_call_chunks and not used_filler and not spoken:
                    if any(c.get("name") == "end_call" for c in chunk.tool_call_chunks):
                        continue
                    used_filler = True
                    yield emit(random.choice(FILLERS))
            else:
                for node, update in data.items():
                    for message in (update or {}).get("messages", []):
                        if node == "agent" and isinstance(message, AIMessage):
                            said_text = bool(_content_text(message.content).strip())
                            for tc in message.tool_calls:
                                tool_args[tc["id"]] = tc["args"]
                                if tc["name"] == "end_call":
                                    # Skip the farewell if the model already said it as text.
                                    hang_up = EndCall(
                                        reason=str(tc["args"].get("reason", "")),
                                        message=""
                                        if said_text
                                        else str(tc["args"].get("message", "")),
                                    )
                        elif node == "tools" and isinstance(message, ToolMessage):
                            _spawn(
                                calls.add_turn(
                                    call.id,
                                    "tool",
                                    _content_text(message.content)[:MAX_TOOL_LOG_CHARS],
                                    tool_name=message.name,
                                    tool_args=tool_args.get(message.tool_call_id),
                                    sources=message.artifact
                                    if isinstance(message.artifact, list)
                                    else None,
                                )
                            )
        if hang_up:
            if req.can_end_call:
                # ElevenLabs speaks the farewell from the tool arguments, then hangs up.
                spoken.append(hang_up.message)
                yield hang_up
            elif hang_up.message:
                yield emit(hang_up.message)
    except asyncio.CancelledError:
        # ElevenLabs cancels the request when the caller interrupts; keep what was said.
        spoken.append(" [interrupted]")
        raise
    except Exception:
        log.exception("Agent turn failed for conversation %s", req.conversation_id)
        yield emit(ERROR_REPLY)
    finally:
        if content := "".join(spoken).strip():
            _spawn(calls.add_turn(call.id, "assistant", content, latency_ms=first_token_ms))
