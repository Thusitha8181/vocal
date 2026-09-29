import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import get_settings
from app.db.models import KnowledgeDocument
from app.db.session import get_session
from app.rag.ingest import ingest_directory, ingest_file
from app.rag.store import asearch

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.get("")
async def list_documents(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    docs = (
        await session.exec(select(KnowledgeDocument).order_by(col(KnowledgeDocument.filename)))
    ).all()
    return [d.model_dump(mode="json") for d in docs]


@router.post("", status_code=202)
async def upload_document(file: UploadFile, background: BackgroundTasks) -> dict[str, str]:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 20 MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "File is not a valid PDF")

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", file.filename or "upload.pdf").strip("-")
    directory = get_settings().knowledge_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / safe_name
    path.write_bytes(data)
    background.add_task(ingest_file, path)
    return {"filename": safe_name, "status": "indexing"}


@router.post("/reindex", status_code=202)
async def reindex(background: BackgroundTasks) -> dict[str, str]:
    background.add_task(ingest_directory)
    return {"status": "indexing"}


@router.get("/search")
async def search(q: str, k: int = 4) -> list[dict[str, Any]]:
    if not q.strip():
        return []
    return [chunk.as_dict() for chunk in await asearch(q, min(k, 10))]
