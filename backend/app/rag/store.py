import asyncio
from dataclasses import asdict, dataclass
from functools import lru_cache

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from app.config import get_settings
from app.rag.embeddings import get_embeddings


@dataclass
class RetrievedChunk:
    content: str
    source: str
    title: str
    page: int
    score: float

    def as_dict(self) -> dict:
        return asdict(self)


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def ensure_collection() -> None:
    settings = get_settings()
    client = get_qdrant_client()
    if client.collection_exists(settings.qdrant_collection):
        return
    dimension = len(get_embeddings().embed_query("dimension probe"))
    client.create_collection(
        settings.qdrant_collection,
        vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
    )
    client.create_payload_index(
        settings.qdrant_collection,
        field_name="metadata.source",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )


@lru_cache
def get_vector_store() -> QdrantVectorStore:
    ensure_collection()
    return QdrantVectorStore(
        client=get_qdrant_client(),
        collection_name=get_settings().qdrant_collection,
        embedding=get_embeddings(),
    )


def search(query: str, k: int | None = None) -> list[RetrievedChunk]:
    results = get_vector_store().similarity_search_with_score(
        query, k=k or get_settings().rag_top_k
    )
    return [
        RetrievedChunk(
            content=doc.page_content,
            source=doc.metadata.get("source", ""),
            title=doc.metadata.get("title", ""),
            page=int(doc.metadata.get("page", 0)),
            score=round(float(score), 4),
        )
        for doc, score in results
    ]


async def asearch(query: str, k: int | None = None) -> list[RetrievedChunk]:
    return await asyncio.to_thread(search, query, k)
