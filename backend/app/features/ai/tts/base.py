"""
TTS Client Interface

What every text-to-speech provider integration implements.
"""

from typing import Protocol


class VoiceRequiredError(ValueError):
    """The provider strictly requires a voice for speech synthesis, but none was given.

    Happens in particular during a plain key test (the API-key "Test" button) — there's no
    project yet at that point, and therefore no project voice. This is its own type instead of a
    generic ValueError so the caller can specifically distinguish it from a real
    configuration/access error, instead of incorrectly marking the key as "error".
    """


class TTSClient(Protocol):
    """A speech-synthesis provider bound to one stored API key."""

    def synthesize(self, text: str, voice: str | None, language: str) -> tuple[bytes, str]:
        """Turn already speech-normalized `text` into audio; returns (audio bytes, content type)."""
        ...
