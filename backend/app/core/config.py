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

from pydantic_settings import BaseSettings, SettingsConfigDict

# Path to the .env-file within the root directory
_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


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