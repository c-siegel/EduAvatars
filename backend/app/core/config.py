"""
Configuration Settings for EduAvatars Backend

This module defines all configuration settings for the backend. Settings are loaded from
the shared root .env file (or real environment variables), validated automatically by
Pydantic Settings.

What are settings?
Settings are typed values the app needs to run — secrets, URLs, feature toggles, file paths —
that differ between your machine and a real deployment. Instead of hardcoding them, they live
in a .env file and get read into this typed `Settings` object once at startup.

Required (no default — the app won't start without them):
- jwt_secret: signs login tokens
- api_key_encryption_secret: encrypts stored provider API keys

Everything else below has a sensible default for local development.

How to use:
    from app.core.config import settings

    if settings.registration_enabled:
        ...
    db_url = settings.database_url
"""

from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Path to the .env-file within the root directory
_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

# Values people copy-paste from .env.example (or type without thinking) — none of these are
# safe JWT secrets, no matter how they're cased, so this is checked in addition to length.
_WEAK_JWT_SECRETS = frozenset(
    {
        "change-me", "changeme", "change_me", "secret", "password", "insecure",
        "your-secret-key", "test", "changethis", "please-change-me",
    }
)


class Settings(BaseSettings):
    
    # Pydantic configuration: read from the shared root .env file, ignore extra environment variables
    model_config = SettingsConfigDict(env_file=_ROOT_ENV_FILE, extra="ignore")

    # ==================== DATABASE SETTINGS ====================
    
    database_url: str = "sqlite:///./eduavatars.db"

    # ==================== JWT AUTHENTICATION SETTINGS ====================
    
    jwt_secret: str
    """
    Secret key used to sign JWT (JSON Web Token) authentication tokens.
    
    This is a REQUIRED setting. Generate a strong random string for production.
    You can generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    """

    jwt_algorithm: str = "HS256"
    """
    Algorithm used to sign JWT tokens.
    Default: "HS256" (HMAC with SHA-256)
    """

    access_token_expire_minutes: int = 10080  # 7 Tage

    # ==================== API KEY ENCRYPTION ====================
    
    api_key_encryption_secret: str
    """
    Secret key used to encrypt API keys stored in the database.

    This is a REQUIRED setting. Generate a strong random string for production.
    You can generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    """

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        """Reject placeholder or too-short secrets so a misconfigured deploy fails at
        startup instead of quietly signing every session token with a guessable key."""
        if len(v) < 32 or v.strip().strip("\"'").lower() in _WEAK_JWT_SECRETS:
            raise ValueError(
                "JWT_SECRET looks like a placeholder or is too short (need at least 32 "
                "random characters). Generate one with: "
                'python3 -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return v

    @field_validator("api_key_encryption_secret")
    @classmethod
    def _validate_api_key_encryption_secret(cls, v: str) -> str:
        """Construct the real Fernet cipher here so an invalid key fails at startup —
        not the first time a user tries to save a provider API key in production."""
        try:
            Fernet(v.encode())
        except Exception as exc:
            raise ValueError(
                "API_KEY_ENCRYPTION_SECRET is not a valid Fernet key. Generate one with: "
                'python3 -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from exc
        return v

    # ==================== CORS SETTINGS ====================
    
    cors_origins: str = "http://localhost:5173"
    """
    Allowed origins for Cross-Origin Resource Sharing (CORS).
    
    Default: "http://localhost:5173" (local development frontend)
    
    This controls which websites can make API requests to your backend.
    Separate multiple origins with commas, e.g.:
    "http://localhost:5173,https://yourdomain.com,https://app.yourdomain.com"
    
    Security: Only add trusted domains. Wildcards like "*" allow any domain (not recommended for production).
    """

    # ==================== ENVIRONMENT SETTINGS ====================
    
    environment: str = "development"
    """
    Current environment mode.
    
    Options:
    - "development": For local development (more verbose logging, debug features)
    - "production": For live deployment (optimized, secure)
    - "testing": For running tests
    
    This affects logging, error messages, and other environment-specific behavior.
    """

    cookie_secure: bool = False
    """
    Whether cookies should only be sent over HTTPS.
    
    Default: False (for development)
    
    Set to True in production (docker-compose.yaml) when using HTTPS. This prevents cookies from being
    sent over unencrypted HTTP connections, improving security.
    """

    # ==================== FILE UPLOAD DIRECTORIES ====================
    
    # Backend-specific directories (not frontend/public/) — Backend and Frontend can be
    # separate deployments/filesystems in institutional hosting environments.
    
    avatar_upload_dir: str = "uploads/avatars"
    """
    Directory where uploaded avatar files are stored.
    This is relative to the backend working directory. Make sure this directory
    exists and is writable by the application.
    """

    profile_picture_upload_dir: str = "uploads/profile-pictures"
    """
    Directory where uploaded user profile pictures are stored.
    This is relative to the backend working directory.
    """

    avatar_thumbnail_upload_dir: str = "uploads/avatar-thumbnails"
    """
    Directory where avatar thumbnail images are stored.
    Thumbnails are smaller versions of avatars for faster loading.
    """

    background_upload_dir: str = "uploads/backgrounds"
    """
    Directory where uploaded background images are stored.
    Background images are used in the chat interface.
    """

    start_audio_upload_dir: str = "uploads/start-audio"
    """
    Directory where a project's once-generated start-prompt audio (see api/projects.py's
    start-audio routes) is stored, so it doesn't need to be re-synthesized on every chat load.
    """

    # ==================== EMAIL & PASSWORD RESET SETTINGS ====================
    
    # For password reset flow (link in email text) and SMTP sending.
    
    frontend_base_url: str = "http://localhost:5173"
    """
    Base URL of the frontend application.
    
    Default: "http://localhost:5173" (local development)
    
    This is used to generate links in emails, such as password reset links.
    Example: If your frontend is at https://app.example.com, set this to that URL.
    """

    # ==================== SMTP-EMAIL Settings ====================
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "no-reply@eduavatars.example"
    smtp_use_tls: bool = True
    password_reset_token_expire_minutes: int = 30

    # ==================== REGISTRATION SETTINGS ====================
    
    # For initial deployment, the instance should only be internally usable
    # (accounts are created manually) — Login remains unaffected, only
    # self-registration is disabled (see api/auth.py).
    
    registration_enabled: bool = True
    """
    Whether new users can register themselves.
    When True: Anyone can create an account via the registration page.

    Only used as the INITIAL value the first time the DB-backed site settings row is created
    (see services/site_settings_service.py) — after that, an admin toggles this from the
    dashboard instead, and this env var no longer has any effect.
    """

    # ==================== ADMIN BOOTSTRAP SETTINGS ====================

    # Set both together to create (or promote) an admin account on startup — see
    # app/cli/bootstrap_admin.py, run from docker/backend-entrypoint.sh. Safe to remove from your
    # .env after the first successful run; the bootstrap is idempotent either way.

    admin_email: str | None = None
    """
    Email of the account to create-or-promote to admin on startup.

    Leave unset to skip admin bootstrapping entirely (e.g. for a second instance that already
    has its admins). Must be set together with admin_password.
    """

    admin_password: str | None = None
    """
    Password for a newly created bootstrap admin account.

    Only used when admin_email doesn't match an existing account yet — promoting an EXISTING
    account to admin never touches their password.
    """

    # ==================== SPEECH-TO-TEXT (STT) SETTINGS ====================
    
    # Speech recognition runs directly in the backend process using the
    # faster-whisper library (see services/stt_service.py) — no separate
    # Whisper container or cloud service needed.
    # stt_model is either a short name ("small", "medium", …) or a Hugging Face
    # repository (like the default) — both are accepted directly by faster-whisper.
    
    stt_model: str = "Systran/faster-whisper-small"
    """
    Speech-to-Text model to use for transcribing audio.
        
    Options:
    - "Systran/faster-whisper-small": Small model, fast, good accuracy (default)
    - "Systran/faster-whisper-medium": Medium model, slower, better accuracy
    - "Systran/faster-whisper-large-v3": Large model, slowest, best accuracy
    - "tiny", "base", "small", "medium", "large": Short names for standard models
    
    The model will be downloaded automatically on first use.
    Larger models are more accurate but require more CPU/memory and are slower.
    """

    stt_model_cache_dir: str = "whisper-cache"
    """
    Directory where the STT model is cached after download.

    The model is downloaded on first use (several hundred MB). This directory
    stores the downloaded model so it doesn't need to be downloaded again.

    Important: In Docker, this must point to a persistent volume (see
    docker/docker-compose.yml), otherwise the model is re-downloaded on every
    container restart.
    """

    stt_max_concurrent_transcriptions: int = 1
    """
    How many Whisper transcriptions may run at the same time, in this one process.

    Whisper is CPU-bound and (with stt_cpu_threads below) each transcription is written to use
    most of the machine's cores — running several at once wouldn't finish any of them faster,
    just make every one slower. Requests beyond this limit wait in line (see
    stt_transcription_queue_timeout_seconds) instead of piling onto the CPU together.
    """

    stt_transcription_queue_timeout_seconds: float = 5.0
    """
    How long a transcription request waits for a free "slot" (see
    stt_max_concurrent_transcriptions above) before giving up.

    A busy 503 lets the visitor retry immediately; queueing indefinitely would instead pile up
    stuck requests behind whichever transcription is currently running.
    """

    stt_cpu_threads: int = 0
    """
    CPU threads faster-whisper's model may use per transcription.

    0 (the default) means "let faster-whisper pick its own default", which uses most of the
    machine's cores per call — fine for a single transcription, but worth capping (e.g. to a
    third of the host's cores) on a shared machine so one transcription doesn't starve the
    request-serving thread pool of CPU while it runs.
    """

    # ==================== PUBLIC CHAT & VOICE INPUT RATE LIMITS ====================

    # Sized for a school class of ~30 students in one 45-minute lesson (see
    # app/core/rate_limit.py). The per-visitor number is the tight, meaningful-per-person
    # limit; the per-IP number is a much higher ceiling since a whole class typically shares
    # one public address behind NAT — it guards against abuse, not normal classroom use.

    chat_window_seconds: int = 600
    """Sliding-window size, in seconds, for the public chat message rate limits below."""

    chat_max_per_visitor: int = 30
    """Public chat messages one visitor (browser tab) may send per chat_window_seconds."""

    chat_max_per_ip: int = 900
    """
    Public chat messages one IP address may send per chat_window_seconds.

    High on purpose: a school class of ~30 students often shares one public IP behind NAT, so
    this has to comfortably cover the whole room's normal traffic, not just one person's.
    """

    transcribe_window_seconds: int = 600
    """Sliding-window size, in seconds, for the voice-transcription rate limits below."""

    transcribe_max_per_visitor: int = 90
    """
    Voice-transcription requests one visitor may send per transcribe_window_seconds.

    The frontend splits one spoken recording into several requests, one per pause it detects
    (see pages/PublicChat/index.tsx) — roughly 2-4 requests per sentence — so this needs to be
    several times the number of sentences a student would actually speak in that window.
    """

    transcribe_max_per_ip: int = 900
    """Voice-transcription requests one IP address may send per transcribe_window_seconds."""

    # ==================== THREAD POOL SIZING ====================

    # Every sync route (almost all of them — see api/*.py) and every streamed chat reply's
    # generator runs in one of these worker threads, not on the event loop itself. Starlette's
    # own default (40) is sized for a handful of simultaneous users, not a school class.

    request_thread_pool_size: int = 100
    """
    How many worker threads FastAPI/Starlette may use at once, across every sync route and
    every /message/stream response body, in this one process.

    Applied to anyio's default thread limiter on startup (see main.py's lifespan) — anyio's own
    default is 40, shared by literally everything that isn't `async def`, which a class of ~30
    concurrently active students (each holding at least one thread for their streamed reply)
    can exhaust on its own.
    """

    tts_stream_worker_pool_size: int = 16
    """
    How many text-to-speech chunks may be synthesized at once, across every /message/stream
    request, in this one process.

    Each streamed reply used to get its own single-worker thread pool for this; now they all
    share one pool sized by this setting, so a burst of simultaneously-streaming students shares
    a bounded resource instead of each spawning an unbounded number of threads.
    """

    # ==================== HELPER PROPERTIES ====================
    
    @property
    def smtp_configured(self) -> bool:
        """
        Check if SMTP is properly configured.
        
        Returns:
            True if smtp_host is set (email features enabled), False otherwise.
        """
        return bool(self.smtp_host)

    @property
    def cors_origin_list(self) -> list[str]:
        """
        Parse CORS origins string into a list.
        
        Returns:
            List of allowed CORS origins, with whitespace trimmed.
        Example:
            If cors_origins = "http://localhost:5173, https://example.com" it 
            returns ["http://localhost:5173", "https://example.com"]
        """
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
"""
Global settings instance.
    
Usage in other modules:
    from app.core.config import settings
    
    # Access settings
    db_url = settings.database_url
    jwt_secret = settings.jwt_secret
"""