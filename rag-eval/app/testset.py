"""
Generating Test Questions from the Material

A teacher rarely has a list of questions with reference answers at hand. This drafts one: for
each sampled passage, the judge LLM writes one question a student might ask that the passage
answers, plus the answer as the passage gives it. The teacher then reviews the drafts in the
dashboard — nothing is used until they approve it.

Ragas has its own test set generator, but it builds a knowledge graph over all documents first
(many LLM and embedding calls before the first question) and still runs on Ragas' legacy LangChain
interface. One call per passage is cheaper, predictable to estimate, and good enough for drafts a
human checks anyway.

How to use:
    cases = await generate_cases(request)
"""

import asyncio
import logging

from pydantic import BaseModel, Field

from app.config import settings
from app.judge import JudgeFailed, make_judge
from app.schemas import GeneratedCase, GenerateRequest, SourceChunk

logger = logging.getLogger(__name__)

# Passages shorter than this (a heading, a page number, a table fragment) rarely carry a fact
# worth asking about.
MIN_CHUNK_CHARS = 80

_LANGUAGE_NAMES = {"de": "German", "en": "English"}

_PROMPT = """You write test questions for a teaching assistant that answers students' questions \
from course material.

Read the passage below and write ONE question a student might realistically ask that this passage \
answers, and the answer as the passage gives it.

Rules:
- The question must be answerable from the passage alone, without seeing it ("According to the \
text…" or "In this section…" are not allowed).
- Ask about the substance, not about the layout, headings or page numbers.
- The answer is 1–3 sentences, uses only facts from the passage, and doesn't quote it at length.
- Write both in {language}.
- If the passage contains no fact worth asking about (e.g. a table of contents), return an empty \
question and an empty answer.

{heading}Passage:
\"\"\"
{text}
\"\"\"
"""


class _QAPair(BaseModel):
    question: str = Field(description="The student's question, or empty")
    answer: str = Field(description="The answer according to the passage, or empty")


def _prompt(chunk: SourceChunk, language: str) -> str:
    heading = f"Section: {chunk.heading}\n\n" if chunk.heading else ""
    return _PROMPT.format(language=_LANGUAGE_NAMES[language], heading=heading, text=chunk.text)


async def generate_cases(request: GenerateRequest) -> list[GeneratedCase]:
    llm = make_judge(request.judge)
    usable = [chunk for chunk in request.chunks if len(chunk.text.strip()) >= MIN_CHUNK_CHARS]
    # The backend sends a random sample; a few spare passages make up for ones the judge skips.
    candidates = usable[: request.size * 2]
    semaphore = asyncio.Semaphore(max(1, settings.rag_eval_concurrency))
    failures = 0

    async def draft(chunk: SourceChunk) -> GeneratedCase | None:
        nonlocal failures
        async with semaphore:
            try:
                pair = await llm.agenerate(_prompt(chunk, request.language), _QAPair)
            except Exception as exc:  # noqa: BLE001 — one failed passage costs one draft
                failures += 1
                logger.warning("Drafting a test question failed: %s", type(exc).__name__)
                return None
        question, answer = pair.question.strip(), pair.answer.strip()
        if not question or not answer:
            return None
        return GeneratedCase(question=question[:4000], reference=answer[:8000], chunk_id=chunk.chunk_id)

    drafts = await asyncio.gather(*(draft(chunk) for chunk in candidates))
    cases = [case for case in drafts if case is not None][: request.size]
    if not cases and candidates and failures == len(candidates):
        # Every call failed — most likely a wrong key or model, which the teacher should see.
        raise JudgeFailed()
    return cases
