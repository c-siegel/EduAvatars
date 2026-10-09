"""
Generating Test Questions

A teacher rarely has a list of questions at hand. This drafts them, in three kinds that test
different things (see app/schemas.py::QuestionKind). The teacher reviews every draft in the
dashboard — nothing is used until they approve it.

- grounded: for each sampled passage, the judge LLM writes one question a student might ask that
  the passage answers, plus the answer as the passage gives it. Tests whether retrieval finds the
  passage. These are easy by construction (the answer is in the material), so the quality
  metrics that compare answer and passage score high — that's what coverage questions are for.
- topic: realistic student questions about the subject, written from the avatar's instructions and
  the titles of the documents but without seeing any content, so questions the material doesn't
  cover can come up. No reference answer: the judge's own knowledge could contradict the course
  material, which would make it a wrong yardstick.
- offtopic: questions outside the subject, to see whether the avatar admits what it doesn't know.

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
- Write the question the way a student would say it, in everyday words, and avoid copying the \
passage's technical terms where a student wouldn't know them yet.
- Write both in {language}.
- If the passage contains no fact worth asking about (e.g. a table of contents), return an empty \
question and an empty answer.

{heading}Passage:
\"\"\"
{text}
\"\"\"
"""


_TOPIC_PROMPT = """You write test questions for a teaching assistant (an AI avatar) that students chat \
with. You are NOT given its course material, on purpose: the questions should be the ones students \
would really ask about the subject, so that gaps in the material show up.

About the assistant:
- Its instructions: \"\"\"{preprompt}\"\"\"
- Project: {project_title}
- Description of the material: {description}
- Titles of the uploaded documents: {documents}
- Learning objectives / level, if the teacher gave any: {objectives}

Write {size} different questions a student might ask this assistant about the subject. Mix easy and \
harder ones, factual questions and "why/how" questions, and a few vaguely or colloquially phrased \
ones. Don't ask only about what the document titles name: include related topics a student \
would plausibly wonder about.
{avoid}
Write them in {language}, one question each, without answers."""

_OFFTOPIC_PROMPT = """You write test questions for a teaching assistant (an AI avatar) that students chat \
with. Its course material covers only one subject.

About the assistant:
- Its instructions: \"\"\"{preprompt}\"\"\"
- Project: {project_title}
- Description of the material: {description}
- Titles of the uploaded documents: {documents}

Write {size} different questions a student might ask that the course material certainly does NOT \
cover. Some should be plainly unrelated (sports, celebrities, everyday life), some close to the \
subject but about a detail or neighbouring field that a course like this wouldn't include, and one \
or two that try to make the assistant claim something the material doesn't say (e.g. asking for an \
exact figure or a quotation from "the script").
{avoid}
Write them in {language}, one question each, without answers."""


class _Questions(BaseModel):
    questions: list[str] = Field(description="The questions, one per entry")


class _QAPair(BaseModel):
    question: str = Field(description="The student's question, or empty")
    answer: str = Field(description="The answer according to the passage, or empty")


def _prompt(chunk: SourceChunk, language: str) -> str:
    heading = f"Section: {chunk.heading}\n\n" if chunk.heading else ""
    return _PROMPT.format(language=_LANGUAGE_NAMES[language], heading=heading, text=chunk.text)


async def generate_cases(request: GenerateRequest) -> list[GeneratedCase]:
    llm = make_judge(request.judge)
    if request.kind != "grounded":
        return await _generate_without_material(request, llm)
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


async def _generate_without_material(request: GenerateRequest, llm) -> list[GeneratedCase]:
    topic = request.topic
    avoid = ""
    if topic.existing_questions:
        listed = "\n".join(f"- {q[:200]}" for q in topic.existing_questions)
        avoid = f"\nThe test set already has these questions; don't repeat them or ask the same thing again:\n{listed}\n"
    template = _TOPIC_PROMPT if request.kind == "topic" else _OFFTOPIC_PROMPT
    prompt = template.format(
        preprompt=topic.preprompt.strip() or "(none)",
        project_title=topic.project_title.strip() or "(none)",
        description=topic.description.strip() or "(none)",
        documents=", ".join(t[:100] for t in topic.document_titles) or "(none)",
        objectives=topic.objectives.strip() or "(none)",
        size=request.size,
        avoid=avoid,
        language=_LANGUAGE_NAMES[request.language],
    )
    try:
        result = await llm.agenerate(prompt, _Questions)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Drafting %s questions failed: %s", request.kind, type(exc).__name__)
        raise JudgeFailed() from exc
    seen: set[str] = set()
    cases = []
    for question in result.questions:
        question = question.strip()
        if question and question.lower() not in seen:
            seen.add(question.lower())
            cases.append(GeneratedCase(question=question[:4000]))
    return cases[: request.size]

