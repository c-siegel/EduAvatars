"""
Embeddings for Answer Relevancy

Answer relevancy has the judge write questions the answer would fit, then compares them with the
real question by embedding similarity. The embeddings come from the knowledge service (POST
/embed), with the knowledge base's own model — local or API — so this service needs no embedding
model or key of its own.

How to use:
    embeddings = RagServiceEmbedding(embedding_config)
    vector = await embeddings.aembed_text("Was ist Photosynthese?")
"""

import typing as t

import httpx
from ragas.embeddings.base import BaseRagasEmbedding

from app.config import settings

_BATCH = 64


class RagServiceEmbedding(BaseRagasEmbedding):
    def __init__(self, config: dict[str, t.Any]) -> None:
        super().__init__()
        self._config = config

    def _request(self) -> dict:
        return {
            "url": f"{settings.rag_service_url.rstrip('/')}/embed",
            "headers": {"Authorization": f"Bearer {settings.rag_service_token}"},
        }

    def embed_text(self, text: str, **kwargs: t.Any) -> list[float]:
        return self.embed_texts([text])[0]

    async def aembed_text(self, text: str, **kwargs: t.Any) -> list[float]:
        return (await self.aembed_texts([text]))[0]

    def embed_texts(self, texts: list[str], **kwargs: t.Any) -> list[list[float]]:
        vectors: list[list[float]] = []
        with httpx.Client(trust_env=False, timeout=60) as client:
            for start in range(0, len(texts), _BATCH):
                request = self._request()
                response = client.post(
                    request["url"],
                    headers=request["headers"],
                    json={"texts": texts[start : start + _BATCH], "embedding": self._config},
                )
                response.raise_for_status()
                vectors.extend(response.json()["vectors"])
        return vectors

    async def aembed_texts(self, texts: list[str], **kwargs: t.Any) -> list[list[float]]:
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(trust_env=False, timeout=60) as client:
            for start in range(0, len(texts), _BATCH):
                request = self._request()
                response = await client.post(
                    request["url"],
                    headers=request["headers"],
                    json={"texts": texts[start : start + _BATCH], "embedding": self._config},
                )
                response.raise_for_status()
                vectors.extend(response.json()["vectors"])
        return vectors
