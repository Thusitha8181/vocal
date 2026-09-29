from functools import lru_cache

from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings

from app.config import get_settings


class FastEmbedEmbeddings(Embeddings):
    """LangChain adapter over FastEmbed: local ONNX embeddings, no API key or GPU required."""

    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()


@lru_cache
def get_embeddings() -> FastEmbedEmbeddings:
    settings = get_settings()
    settings.embedding_cache_dir.mkdir(parents=True, exist_ok=True)
    return FastEmbedEmbeddings(
        settings.embedding_model, cache_dir=str(settings.embedding_cache_dir)
    )
