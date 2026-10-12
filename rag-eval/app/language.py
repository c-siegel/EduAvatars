"""
Judge Prompts in the Material's Language

Ragas' prompts are English, with English few-shot examples. For German material the judge then
tends to extract English statements from German answers and compare them against German
passages — which works, but less reliably. Ragas can translate a prompt's examples; that costs
judge calls, so each translated prompt is cached on disk (one JSON file per metric, prompt,
language and judge) and reused by later runs.

The cache is per judge model and endpoint, not shared across all of them: the examples steer
every later score, and a teacher can point a judge at their own endpoint. Its translations must
only ever be used for runs judged through that same endpoint.

The instructions themselves stay English: models follow English meta-instructions reliably, and
translating them would change what the metric measures.

How to use:
    await adapt_metric(metric, "de", llm, judge_config)
"""

import asyncio
import copy
import hashlib
import json
import logging
from pathlib import Path

from ragas.prompt.metrics.base_prompt import BasePrompt

from app.config import settings
from app.schemas import JudgeConfig

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES = {"de": "german"}
_locks: dict[str, asyncio.Lock] = {}


def _cache_dir() -> Path:
    path = Path(settings.rag_eval_data_dir) / "prompt-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _prompts(metric) -> dict[str, BasePrompt]:
    return {name: value for name, value in vars(metric).items() if isinstance(value, BasePrompt)}


def judge_cache_id(judge: JudgeConfig) -> str:
    """Identifies the judge by model and endpoint — never by its key."""
    return hashlib.sha256(f"{judge.model}|{judge.api_base or ''}".encode()).hexdigest()[:16]


async def adapt_metric(metric, language: str, llm, judge: JudgeConfig) -> None:
    """Swap the metric's prompts for versions with translated examples (cached per judge)."""
    target = _LANGUAGE_NAMES.get(language)
    if target is None:
        return
    for attribute, prompt in _prompts(metric).items():
        key = f"{type(metric).__name__}.{attribute}.{language}.{judge_cache_id(judge)}"
        lock = _locks.setdefault(key, asyncio.Lock())
        async with lock:
            path = _cache_dir() / f"{key}.json"
            if path.exists():
                adapted = _load(prompt, path)
            else:
                try:
                    adapted = await prompt.adapt(target, llm)
                except Exception as exc:  # noqa: BLE001
                    # A failed translation isn't worth failing the run: the English prompt works,
                    # just a little less reliably for German material. Retried next run.
                    logger.warning("Couldn't translate judge prompt %s: %s", key, type(exc).__name__)
                    continue
                _save(adapted, path)
                logger.info("Translated judge prompt %s", key)
        setattr(metric, attribute, adapted)


def _save(prompt: BasePrompt, path: Path) -> None:
    examples = [[i.model_dump(), o.model_dump()] for i, o in prompt.examples]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"language": prompt.language, "examples": examples}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _load(prompt: BasePrompt, path: Path) -> BasePrompt:
    data = json.loads(path.read_text(encoding="utf-8"))
    adapted = copy.deepcopy(prompt)
    adapted.examples = [
        (prompt.input_model.model_validate(i), prompt.output_model.model_validate(o)) for i, o in data["examples"]
    ]
    adapted.language = data["language"]
    return adapted
