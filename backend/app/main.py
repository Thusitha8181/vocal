import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.agent.runner import wait_for_background
from app.api import dashboard, knowledge, llm, voice, webhooks
from app.config import get_settings
from app.db.session import get_engine
from app.rag.store import get_qdrant_client, get_vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("vocal")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not get_settings().groq_api_key:
        log.warning("GROQ_API_KEY is not set; the agent will reply with an error message")
    # Load the embedding model and connect to Qdrant up front so the first caller isn't slowed.
    try:
        await asyncio.to_thread(get_vector_store)
    except Exception:
        log.exception("Vector store warm-up failed; knowledge search will retry on first use")
    yield
    await wait_for_background()
    await get_engine().dispose()


app = FastAPI(title="Vocal", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(llm.router)
app.include_router(webhooks.router)
app.include_router(dashboard.router)
app.include_router(knowledge.router)
app.include_router(voice.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    status = {"api": "ok"}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["postgres"] = "ok"
    except Exception as exc:
        status["postgres"] = f"error: {exc.__class__.__name__}"
    try:
        await asyncio.to_thread(get_qdrant_client().get_collections)
        status["qdrant"] = "ok"
    except Exception as exc:
        status["qdrant"] = f"error: {exc.__class__.__name__}"
    return status
