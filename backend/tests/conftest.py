"""Integration test fixtures: a dedicated Postgres database and Qdrant collection.

Requires `docker compose up -d postgres qdrant`. No LLM or ElevenLabs keys are needed; the
agent runs against a scripted fake chat model (see tests/fakes.py).
"""

import os

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://vocal:vocal@localhost:5432/vocal_test"
)
os.environ["QDRANT_COLLECTION"] = "lauki_knowledge_test"
os.environ["CUSTOM_LLM_API_KEY"] = "test-llm-key"
os.environ["ELEVENLABS_WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["DEMO_CUSTOMER_PHONE"] = ""

import asyncio  # noqa: E402
from pathlib import Path  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.seed import seed  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.rag.ingest import ingest_directory  # noqa: E402
from app.rag.store import get_qdrant_client, get_vector_store  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _migrate() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
async def database():
    async with get_engine().begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await get_engine().dispose()
    # Alembic's env.py runs its own event loop, so run it off the test loop.
    await asyncio.to_thread(_migrate)
    await seed()
    yield
    await get_engine().dispose()


@pytest.fixture(scope="session")
async def knowledge(database):
    client = get_qdrant_client()
    collection = os.environ["QDRANT_COLLECTION"]
    if client.collection_exists(collection):
        client.delete_collection(collection)
    get_vector_store.cache_clear()
    await ingest_directory()
    yield


@pytest.fixture
async def api():
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
