"""OpenAI-compatible chat completions endpoint used by ElevenLabs as a "Custom LLM"."""

import json
import secrets
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent.graph import get_graph
from app.agent.runner import EndCall, parse_chat_request, run_turn
from app.config import Settings, get_settings

router = APIRouter(tags=["custom-llm"])


def require_llm_key(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.custom_llm_api_key
    if not expected:
        return
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")


def _chunk(completion_id: str, model: str, delta: dict[str, Any], finish: str | None = None) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload)}\n\n"


def _end_call_tool_call(end: EndCall) -> dict[str, Any]:
    args = {"reason": end.reason} | ({"message": end.message} if end.message else {})
    return {
        "id": f"call_{uuid.uuid4().hex[:24]}",
        "type": "function",
        "function": {"name": "end_call", "arguments": json.dumps(args)},
    }


@router.post("/v1/chat/completions", dependencies=[Depends(require_llm_key)])
async def chat_completions(request: Request):
    body = await request.json()
    turn = parse_chat_request(body)
    model = body.get("model") or get_settings().groq_model
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    deltas = run_turn(turn, get_graph())

    if not body.get("stream", False):
        parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        async for delta in deltas:
            if isinstance(delta, EndCall):
                tool_calls.append(_end_call_tool_call(delta))
            else:
                parts.append(delta)
        message: dict[str, Any] = {"role": "assistant", "content": "".join(parts)}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return JSONResponse(
            {
                "id": completion_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls" if tool_calls else "stop",
                    }
                ],
            }
        )

    async def event_stream() -> AsyncIterator[str]:
        yield _chunk(completion_id, model, {"role": "assistant", "content": ""})
        finish = "stop"
        async for delta in deltas:
            if isinstance(delta, EndCall):
                finish = "tool_calls"
                call = _end_call_tool_call(delta) | {"index": 0}
                yield _chunk(completion_id, model, {"tool_calls": [call]})
            else:
                yield _chunk(completion_id, model, {"content": delta})
        yield _chunk(completion_id, model, {}, finish=finish)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
