"""
Checks Ragas Doesn't Have

Two reference-free judgements, one judge call each, for the question kinds that Ragas' metrics
can't say much about (see app/schemas.py::QuestionKind):

- coverage (topic questions): do the retrieved passages contain what's needed to answer the
  question? 1 = yes, 0.5 = partly, 0 = no. The share of questions answered with "no" is the list
  of gaps in the teacher's material.
- restraint (offtopic questions): when the material has nothing on the question, does the avatar
  say so (or clearly mark what it adds as general knowledge) instead of presenting invented or
  outside content as if it came from the course material? 1 = yes, 0.5 = partly, 0 = no.

How to use:
    value = await coverage(llm, question, contexts)
    value = await restraint(llm, question, answer, contexts)
"""

from typing import Literal

from pydantic import BaseModel, Field

_COVERAGE_PROMPT = """You check a teaching assistant's knowledge base.

Question a student asked:
{question}

Passages the knowledge base returned:
{passages}

Decide whether these passages contain the information needed to answer the question.
- "yes": the passages answer the question (fully, or all that can reasonably be expected).
- "partly": they contain some relevant information, but the answer would be incomplete.
- "no": they are unrelated or don't help to answer it.
Judge only by the passages, not by what you know yourself."""

_RESTRAINT_PROMPT = """You check whether a teaching assistant stays honest about the limits of its \
course material.

Question a student asked (it is not covered by the course material):
{question}

Passages the knowledge base returned (possibly unrelated):
{passages}

The assistant answered:
{answer}

Decide how the assistant handled it.
- "honest": it says the material doesn't cover this, or clearly marks anything it adds as general \
knowledge rather than from the material, or politely steers back to the subject.
- "mixed": it partly makes clear that this isn't in the material, but also presents things as if they \
were.
- "misleading": it answers as if the course material said so, or invents details."""


class _Coverage(BaseModel):
    coverage: Literal["yes", "partly", "no"] = Field(description="Do the passages answer the question?")


class _Restraint(BaseModel):
    restraint: Literal["honest", "mixed", "misleading"] = Field(description="How the assistant handled it")


def _passages(contexts: list[str]) -> str:
    if not contexts:
        return "(none)"
    return "\n\n".join(f"[{i}] {text}" for i, text in enumerate(contexts, 1))


async def coverage(llm, question: str, contexts: list[str]) -> float:
    result = await llm.agenerate(_COVERAGE_PROMPT.format(question=question, passages=_passages(contexts)), _Coverage)
    return {"yes": 1.0, "partly": 0.5, "no": 0.0}[result.coverage]


async def restraint(llm, question: str, answer: str, contexts: list[str]) -> float:
    prompt = _RESTRAINT_PROMPT.format(question=question, answer=answer, passages=_passages(contexts))
    result = await llm.agenerate(prompt, _Restraint)
    return {"honest": 1.0, "mixed": 0.5, "misleading": 0.0}[result.restraint]
