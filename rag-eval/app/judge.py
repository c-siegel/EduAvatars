"""
The Judge LLM

Ragas' metrics ask an LLM to break answers into statements, check them against passages, and so
on, and expect structured (JSON) replies. This builds that LLM from the teacher's key: litellm
reaches any provider the backend supports, and instructor parses the replies into Ragas'
response models.

Instructor's MD_JSON mode puts the JSON schema into the prompt and reads a JSON block from the
reply. Function calling or a JSON response format would be stricter, but not every provider or
self-hosted model supports them; plain prompting works with all of them.

How to use:
    llm = make_judge(JudgeConfig(model="openai/gpt-4o", api_key="…"))
    result = await llm.agenerate(prompt, SomeResponseModel)
"""

import instructor
import litellm
from ragas.llms import llm_factory
from ragas.llms.base import InstructorBaseRagasLLM

from app.config import settings
from app.schemas import JudgeConfig


class JudgeFailed(Exception):
    """The judge LLM couldn't be reached or didn't produce a usable reply."""


def make_judge(config: JudgeConfig) -> InstructorBaseRagasLLM:
    # litellm.acompletion is looked up at call time (not bound here), so tests can replace it.
    async def completion(**kwargs):
        return await litellm.acompletion(**kwargs)

    client = instructor.from_litellm(completion, mode=instructor.Mode.MD_JSON)
    # Instructor re-asks up to three times when a reply doesn't parse. Each retry is a paid call
    # and a judge that fails twice will usually fail again, so one retry is the compromise.
    model_args = {"temperature": 0, "timeout": settings.rag_eval_llm_timeout_seconds, "max_retries": 1}
    if config.api_key is not None:
        model_args["api_key"] = config.api_key.get_secret_value()
    if config.api_base:
        model_args["api_base"] = config.api_base
    return llm_factory(config.model, provider="litellm", client=client, adapter="litellm", **model_args)
