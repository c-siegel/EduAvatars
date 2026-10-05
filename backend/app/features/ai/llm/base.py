"""
LLM Client Interface

What every LLM provider integration implements, and the request it receives.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatRequest:
    """One chat turn to send to an LLM: the project's prompt setup plus the new message."""

    preprompt: str
    message: str
    temperature: float | None = None
    top_p: float | None = None
    start_prompt: str | None = None
    history: list[dict] | None = None


class LLMClient(Protocol):
    """A chat-completion provider bound to one stored API key."""

    def complete(self, request: ChatRequest) -> str:
        """Send the request and return the full reply text."""
        ...

    def stream(self, request: ChatRequest) -> Iterator[str]:
        """Send the request and yield the reply text as it arrives."""
        ...

    def test(self) -> None:
        """Try the key with a minimal real call; raises on an invalid key or provider error."""
        ...
