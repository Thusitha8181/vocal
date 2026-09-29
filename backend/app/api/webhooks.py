import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.services.calls import complete_call

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

SIGNATURE_TOLERANCE_SECONDS = 30 * 60


def verify_signature(secret: str, header: str, body: bytes, now: float | None = None) -> bool:
    """Validate an `ElevenLabs-Signature: t=<unix>,v0=<hex hmac>` header."""
    parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    timestamp, signature = parts.get("t"), parts.get("v0")
    if not timestamp or not signature or not timestamp.isdigit():
        return False
    if abs((now or time.time()) - int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/elevenlabs/post-call", status_code=status.HTTP_200_OK)
async def elevenlabs_post_call(
    request: Request,
    elevenlabs_signature: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    body = await request.body()
    if settings.elevenlabs_webhook_secret:
        if not elevenlabs_signature or not verify_signature(
            settings.elevenlabs_webhook_secret, elevenlabs_signature, body
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")
    elif settings.app_env != "development":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook secret not configured")

    event = json.loads(body)
    if event.get("type") != "post_call_transcription":
        return {"status": "ignored"}

    data = event.get("data") or {}
    conversation_id = data.get("conversation_id")
    if not conversation_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing conversation_id")
    await complete_call(conversation_id, data)
    log.info("Stored post-call transcript for %s", conversation_id)
    return {"status": "ok"}
