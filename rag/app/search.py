"""
Hybrid Search

Vector search finds passages that mean the same thing in other words; keyword search (FTS5,
BM25) finds exact terms embeddings tend to blur — names, numbers, technical terms, German compound
words. Both lists are merged with reciprocal rank fusion (RRF): each hit scores 1/(60 + rank) per
list it appears in, so agreement between the two methods counts most and neither method's raw
scores (which aren't comparable) need calibrating.

How to use:
    passages = hybrid_search(store, kb_ids, "Was ist Photosynthese?", top_k=4, config=config)
"""

import re

from app.config import settings
from app.embedding import get_embedder
from app.schemas import EmbeddingConfig, Passage
from app.store import Store

_CANDIDATES = 20
_RRF_K = 60
_WORD_RE = re.compile(r"\w{2,}", re.UNICODE)
_MAX_KEYWORDS = 24

# Function words in German and English. Without this, the OR query below would match nearly every
# chunk for "Was ist das?" and keyword search would return arbitrary passages for small talk.
_STOPWORDS = frozenset(
    """
    der die das den dem des ein eine einer eines einem einen und oder aber ist sind war waren wird
    werden hat haben hatte kann können muss soll sollte wie was wer wo wann warum wieso welche
    welcher welches mit von zu zum zur im in am an auf aus bei für über unter nach vor durch um
    nicht kein keine auch noch nur schon sehr mehr dann denn doch ja nein ich du er sie es wir ihr
    mich mir dich dir sich uns euch mein dein sein ihr unser bitte danke hallo gibt mal gerne
    the a an and or but is are was were be been being has have had do does did can could should
    would will what who where when why how which with of to in on at by for from about into
    not no yes also only very more then than this that these those it its i you he she we they me
    my your our their please thanks thank hello hi there here
    """.split()
)


def fts_query(text: str) -> str | None:
    """A safe FTS5 MATCH expression: each word quoted (so FTS5 syntax in user input is inert),
    OR-combined so a passage needn't contain every word of a conversational question."""
    words = []
    for word in _WORD_RE.findall(text.lower()):
        if word not in words and word not in _STOPWORDS:
            words.append(word)
    if not words:
        return None
    return " OR ".join(f'"{w}"' for w in words[:_MAX_KEYWORDS])


def hybrid_search(store: Store, kb_ids: list[str], query: str, top_k: int, config: EmbeddingConfig) -> list[Passage]:
    dimensions = store.check_query_config(kb_ids, config)
    if dimensions is None:
        # No KB in the list has a single indexed chunk yet — nothing to find, and no reason to
        # load or call an embedding model.
        return []

    scores: dict[int, float] = {}

    vector = get_embedder(config).embed_query(query)
    vector_hits = [
        hit
        for hit in store.vector_search(kb_ids, dimensions, vector, _CANDIDATES)
        if hit[1] <= settings.rag_max_vector_distance
    ]
    for rank, (chunk_id, _distance) in enumerate(vector_hits):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

    match = fts_query(query)
    if match:
        for rank, (chunk_id, _bm25) in enumerate(store.keyword_search(kb_ids, match, _CANDIDATES)):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

    best = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
    rows = store.chunks_by_id([chunk_id for chunk_id, _ in best])
    return [
        Passage(
            chunk_id=chunk_id,
            document_id=rows[chunk_id]["document_id"],
            knowledge_base_id=rows[chunk_id]["knowledge_base_id"],
            text=rows[chunk_id]["text"],
            page=rows[chunk_id]["page"],
            heading=rows[chunk_id]["heading"],
            score=round(score, 6),
        )
        for chunk_id, score in best
        if chunk_id in rows
    ]
