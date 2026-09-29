import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings

router = APIRouter(prefix="/api/voice", tags=["voice"])

ELEVENLABS_API = "https://api.elevenlabs.io/v1"


@router.get("/session")
async def voice_session(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Mint a short-lived WebRTC conversation token so the browser never sees our API key."""
    if not settings.elevenlabs_api_key or not settings.elevenlabs_agent_id:
        raise HTTPException(
            503, "ElevenLabs is not configured. Set ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID."
        )
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{ELEVENLABS_API}/convai/conversation/token",
            params={"agent_id": settings.elevenlabs_agent_id},
            headers={"xi-api-key": settings.elevenlabs_api_key},
        )
    if response.status_code != 200:
        raise HTTPException(502, f"ElevenLabs token request failed: {response.text[:200]}")
    return {
        "agent_id": settings.elevenlabs_agent_id,
        "conversation_token": response.json()["token"],
    }
