"""
Configuration Settings for the Local TTS Sidecar

Typed settings for this service, read from environment variables (all prefixed "TTS_", set in
docker/docker-compose.yml). Kept deliberately small — unlike the main backend, this service has
no database and no secrets.

How to use:
    from app.config import settings

    tts = SoproTTS.from_pretrained(settings.model_repo, cache_dir=settings.model_cache_dir)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TTS_", extra="ignore")

    model_repo: str = "samuel-vitorino/sopro-v2-turbo"
    """Hugging Face repo ID for the sopro model weights, passed straight to SoproTTS.from_pretrained."""

    model_cache_dir: str = "/data/model-cache"
    """
    Where downloaded model weights are cached (mirrors the backend's STT_MODEL_CACHE_DIR).

    Must point at a persistent volume in Docker (see docker/docker-compose.yml) — otherwise the
    ~600MB model is re-downloaded from Hugging Face on every container restart.
    """

    voices_dir: str = "/data/voices"
    """
    Directory holding one bundled reference clip per supported language, named "<language>.wav"
    (e.g. "de.wav") — see voices/README.md for what makes a good reference clip.

    Deliberately not baked into the Docker image: shipping a specific person's voice as the
    product's default would be a real content/licensing decision, not a code decision. An
    operator supplies their own clip(s) here before enabling local TTS.
    """

    custom_voices_dir: str = "/data/custom-voices"
    """
    Where reference clips sent by the backend are kept (see PUT /voices in app/main.py), named by
    their SHA-256 hash. The backend owns these clips (teachers upload them in the dashboard) and
    re-sends one whenever it's missing here, so this directory is only a cache — safe to clear.
    """

    max_voice_bytes: int = 10 * 1024 * 1024
    """Upper bound for one reference clip; the backend already limits clips to 30 s of WAV."""

    quantization: str | None = None
    """
    None (default, full precision) or "int8" for lower CPU/RAM use at some quality cost.

    Only the default has actually been latency/RTF-tested (see the project's local-TTS plan) —
    int8 is offered for weaker hosts but its quality trade-off hasn't been verified here.
    """

    max_concurrent_synthesis: int = 1
    """
    How many synthesis requests may run at the same time, in this one process.

    Sopro is CPU-bound, same reasoning as the backend's faster-whisper semaphore
    (stt_max_concurrent_transcriptions) — running several at once makes each one slower rather
    than finishing more work sooner.
    """

    synthesis_queue_timeout_seconds: float = 5.0
    """How long a synthesis request waits for a free slot (see max_concurrent_synthesis) before giving up."""


settings = Settings()
