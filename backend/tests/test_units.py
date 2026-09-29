import hashlib
import hmac
import time

import pytest

from app.agent.runner import parse_chat_request
from app.api.webhooks import verify_signature
from app.db.models import CallChannel
from app.services.phone import normalize_phone, same_number


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("98765 43210", "+919876543210"),
        ("+91-98765-43210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("+94 77 123 4567", "+94771234567"),
        ("no digits", None),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_same_number_ignores_country_code():
    assert same_number("+919876543210", "9876543210")
    assert not same_number("+919876543210", "+919876543211")


def _sign(secret: str, body: bytes, ts: int) -> str:
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v0={digest}"


def test_verify_signature():
    body, now = b'{"type":"post_call_transcription"}', int(time.time())
    assert verify_signature("s3cret", _sign("s3cret", body, now), body)
    assert not verify_signature("s3cret", _sign("wrong", body, now), body)
    assert not verify_signature("s3cret", _sign("s3cret", body, now - 3600), body)
    assert not verify_signature("s3cret", "garbage", body)


def test_parse_chat_request_reads_elevenlabs_context():
    body = {
        "messages": [
            {
                "role": "system",
                "content": "Vocal context\nconversation_id: conv_123\ncaller_id: +919876543210",
            },
            {"role": "assistant", "content": "Hi, this is Maya from Lauki Phones."},
            {"role": "user", "content": "What's my bill?"},
        ],
        "tools": [{"type": "function", "function": {"name": "end_call"}}],
    }
    req = parse_chat_request(body)
    assert req.conversation_id == "conv_123"
    assert req.caller_number == "+919876543210"
    assert req.channel == CallChannel.phone
    assert req.can_end_call
    assert [m.type for m in req.history] == ["ai", "human"]


def test_parse_chat_request_ignores_unrendered_variables():
    body = {
        "messages": [
            {
                "role": "system",
                "content": "conversation_id: conv_web\ncaller_id: {{system__caller_id}}",
            },
            {"role": "user", "content": "hello"},
        ]
    }
    req = parse_chat_request(body)
    assert req.conversation_id == "conv_web"
    assert req.caller_number is None
    assert req.channel == CallChannel.web
    assert not req.can_end_call
