"""Ingest PDFs from the knowledge directory into Qdrant and track them in Postgres.

Run: uv run python -m app.rag.ingest [--file some.pdf]
"""

import argparse
import asyncio
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from qdrant_client import models
from sqlmodel import select

from app.config import get_settings
from app.db.models import KnowledgeDocument, utcnow
from app.db.session import session_scope
from app.rag.store import get_qdrant_client, get_vector_store

CHUNK_NAMESPACE = uuid.UUID("6f1c2f1e-7d4a-4c1b-9a51-2f3c1f0b9e11")

splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)


@dataclass
class IngestResult:
    filename: str
    title: str
    pages: int
    chunks: int


def _clean(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _title(first_page: str, fallback: str) -> str:
    lines = [line.strip() for line in first_page.splitlines() if line.strip()]
    return " - ".join(lines[:2]) if lines else fallback


def load_pdf(path: Path) -> tuple[str, list[Document]]:
    reader = PdfReader(path)
    pages = [_clean(page.extract_text() or "") for page in reader.pages]
    title = _title(pages[0] if pages else "", path.stem)
    docs: list[Document] = []
    for page_number, text in enumerate(pages, start=1):
        for chunk in splitter.split_text(text):
            # A contextual header on every chunk improves retrieval for short, table-heavy pages.
            docs.append(
                Document(
                    page_content=f"{title}\n\n{chunk}",
                    metadata={"source": path.name, "title": title, "page": page_number},
                )
            )
    return title, docs


def index_file(path: Path) -> IngestResult:
    title, docs = load_pdf(path)
    store = get_vector_store()
    get_qdrant_client().delete(
        get_settings().qdrant_collection,
        points_selector=models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.source", match=models.MatchValue(value=path.name)
                )
            ]
        ),
    )
    ids = [str(uuid.uuid5(CHUNK_NAMESPACE, f"{path.name}:{i}")) for i in range(len(docs))]
    if docs:
        store.add_documents(docs, ids=ids)
    pages = max((d.metadata["page"] for d in docs), default=0)
    return IngestResult(filename=path.name, title=title, pages=pages, chunks=len(docs))


async def ingest_file(path: Path) -> KnowledgeDocument:
    async with session_scope() as session:
        doc = (
            await session.exec(
                select(KnowledgeDocument).where(KnowledgeDocument.filename == path.name)
            )
        ).first() or KnowledgeDocument(filename=path.name, title=path.stem)
        doc.status = "indexing"
        doc.error = None
        session.add(doc)
        await session.commit()

        try:
            result = await asyncio.to_thread(index_file, path)
        except Exception as exc:  # surface failures in the dashboard instead of crashing
            doc.status = "failed"
            doc.error = str(exc)
        else:
            doc.title = result.title
            doc.pages = result.pages
            doc.chunks = result.chunks
            doc.status = "indexed"
            doc.indexed_at = utcnow()
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        return doc


async def ingest_directory(directory: Path | None = None) -> list[KnowledgeDocument]:
    directory = directory or get_settings().knowledge_dir
    return [await ingest_file(path) for path in sorted(directory.glob("*.pdf"))]


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Index knowledge-base PDFs into Qdrant")
    parser.add_argument("--file", type=Path, help="Index a single PDF instead of the whole folder")
    args = parser.parse_args()
    docs = [await ingest_file(args.file)] if args.file else await ingest_directory()
    for doc in docs:
        print(f"{doc.status:>8}  {doc.filename}  ({doc.chunks} chunks)  {doc.error or ''}")


if __name__ == "__main__":
    asyncio.run(_main())
