import hashlib
import hmac
import json
import time
import uuid

import pytest
from langchain_core.messages import AIMessage

from app.agent.graph import build_graph
from app.agent.runner import FILLERS, wait_for_background
from app.api import llm as llm_api
from tests.fakes import ScriptedChatModel, tool_call

AUTH = {"Authorization": "Bearer test-llm-key"}


def _use_script(monkeypatch, *responses: AIMessage) -> ScriptedChatModel:
    model = ScriptedChatModel(responses=list(responses))
    graph = build_graph(model)
    monkeypatch.setattr(llm_api, "get_graph", lambda: graph)
    return model


def _parse_sse(body: str) -> tuple[str, list[dict], list[str]]:
    text, tool_calls, finishes = "", [], []
    for line in body.splitlines():
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        choice = json.loads(line[6:])["choices"][0]
        text += choice["delta"].get("content") or ""
        tool_calls += choice["delta"].get("tool_calls") or []
        if choice["finish_reason"]:
            finishes.append(choice["finish_reason"])
    return text, tool_calls, finishes


def _request(conversation_id: str, user_text: str, **extra) -> dict:
    return {
        "model": "vocal",
        "stream": True,
        "messages": [
            {"role": "system", "content": f"conversation_id: {conversation_id}"},
            {"role": "assistant", "content": "Hi, this is Maya from Lauki Phones."},
            {"role": "user", "content": user_text},
        ],
        **extra,
    }


async def test_rejects_missing_api_key(api):
    response = await api.post("/v1/chat/completions", json=_request("x", "hi"))
    assert response.status_code == 401


async def test_rag_turn_streams_filler_then_answer_and_logs_turns(api, knowledge, monkeypatch):
    model = _use_script(
        monkeypatch,
        tool_call("search_knowledge_base", query="late payment fee"),
        AIMessage("The late fee is fifty rupees, added to your next bill."),
    )
    conversation_id = f"conv-{uuid.uuid4()}"

    response = await api.post(
        "/v1/chat/completions", json=_request(conversation_id, "Is there a late fee?"), headers=AUTH
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.rstrip().endswith("data: [DONE]")

    text, tool_calls, finishes = _parse_sse(response.text)
    assert any(text.startswith(f) for f in FILLERS)
    assert text.endswith("The late fee is fifty rupees, added to your next bill.")
    assert tool_calls == [] and finishes == ["stop"]

    # The second LLM call must see the retrieved policy text from the tool.
    tool_result = model.calls[1][-1]
    assert tool_result.type == "tool" and "Rs. 50" in tool_result.content

    await wait_for_background()
    calls = (await api.get("/api/calls")).json()
    call = next(c for c in calls if c["conversation_id"] == conversation_id)
    detail = (await api.get(f"/api/calls/{call['id']}")).json()
    roles = [t["role"] for t in detail["turns"]]
    assert roles == ["assistant", "user", "tool", "assistant"]
    tool_turn = detail["turns"][2]
    assert tool_turn["tool_name"] == "search_knowledge_base"
    assert tool_turn["sources"][0]["source"].endswith(".pdf")
    assert detail["turns"][3]["latency_ms"] is not None


async def test_end_call_is_forwarded_to_elevenlabs(api, monkeypatch):
    _use_script(
        monkeypatch,
        tool_call("end_call", reason="caller done", message="Thanks for calling Lauki, goodbye!"),
    )
    body = _request(
        f"conv-{uuid.uuid4()}",
        "No that's all, bye",
        tools=[{"type": "function", "function": {"name": "end_call", "parameters": {}}}],
    )
    response = await api.post("/v1/chat/completions", json=body, headers=AUTH)
    text, tool_calls, finishes = _parse_sse(response.text)

    assert text == ""
    assert finishes == ["tool_calls"]
    assert tool_calls[0]["function"]["name"] == "end_call"
    args = json.loads(tool_calls[0]["function"]["arguments"])
    assert args["message"] == "Thanks for calling Lauki, goodbye!"


async def test_end_call_without_elevenlabs_tool_speaks_farewell(api, monkeypatch):
    _use_script(monkeypatch, tool_call("end_call", reason="done", message="Goodbye!"))
    body = _request(f"conv-{uuid.uuid4()}", "bye") | {"stream": False}
    response = await api.post("/v1/chat/completions", json=body, headers=AUTH)
    message = response.json()["choices"][0]["message"]
    assert message["content"] == "Goodbye!"
    assert "tool_calls" not in message


def _signed(body: bytes) -> dict[str, str]:
    ts = int(time.time())
    digest = hmac.new(b"test-webhook-secret", f"{ts}.".encode() + body, hashlib.sha256)
    return {"ElevenLabs-Signature": f"t={ts},v0={digest.hexdigest()}"}


@pytest.mark.parametrize("signed", [True, False])
async def test_post_call_webhook(api, signed):
    conversation_id = f"conv-{uuid.uuid4()}"
    payload = {
        "type": "post_call_transcription",
        "data": {
            "agent_id": "agent_test",
            "conversation_id": conversation_id,
            "status": "done",
            "transcript": [
                {"role": "agent", "message": "Hi, this is Maya.", "time_in_call_secs": 0},
                {"role": "user", "message": "What's my bill?", "time_in_call_secs": 3},
            ],
            "metadata": {
                "start_time_unix_secs": int(time.time()) - 90,
                "call_duration_secs": 90,
                "phone_call": {"external_number": "+919900112233"},
            },
            "analysis": {
                "transcript_summary": "Caller asked about bill.",
                "call_successful": "success",
            },
        },
    }
    body = json.dumps(payload).encode()
    headers = _signed(body) if signed else {"ElevenLabs-Signature": "t=1,v0=bad"}
    response = await api.post("/webhooks/elevenlabs/post-call", content=body, headers=headers)

    if not signed:
        assert response.status_code == 401
        return
    assert response.status_code == 200
    call = next(
        c for c in (await api.get("/api/calls")).json() if c["conversation_id"] == conversation_id
    )
    assert call["status"] == "completed"
    assert call["duration_seconds"] == 90
    assert call["channel"] == "phone"
    assert call["customer_name"] == "Ananya Iyer"
    assert call["successful"] is True


async def test_dashboard_endpoints(api, knowledge):
    assert (await api.get("/health")).json() == {"api": "ok", "postgres": "ok", "qdrant": "ok"}
    customers = (await api.get("/api/customers")).json()
    assert {c["full_name"] for c in customers} >= {"Priya Sharma", "Arjun Mehta"}
    docs = (await api.get("/api/knowledge")).json()
    assert {d["status"] for d in docs} == {"indexed"}
    hits = (await api.get("/api/knowledge/search", params={"q": "5G in Mumbai"})).json()
    assert hits[0]["source"] == "lauki-network-coverage.pdf"
    stats = (await api.get("/api/stats")).json()
    assert stats["total_calls"] >= 1
