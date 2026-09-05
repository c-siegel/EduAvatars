"""
Encrypting and Masking Stored API Keys

Thin wrapper around app/core/security.py's encryption functions, used whenever an API key is
stored or displayed. Keeping this as its own module (instead of importing security.py directly
everywhere) makes it obvious, from the import alone, which code touches raw API key secrets.

How to use:
    from app.services.crypto_service import mask_key, store_api_key

    encrypted = store_api_key(plaintext)
    display_value = mask_key(plaintext)  # e.g. "••••••••1234"
"""

from app.core.security import decrypt_api_key, encrypt_api_key


def mask_key(plaintext: str) -> str:
    """Turn a plaintext key into a display-safe masked version, e.g. "••••••••1234"."""
    if len(plaintext) <= 4:
        return "•" * len(plaintext)
    return "•" * (len(plaintext) - 4) + plaintext[-4:]


def store_api_key(plaintext: str) -> str:
    """Encrypt a plaintext API key for storage."""
    return encrypt_api_key(plaintext)


def reveal_api_key(ciphertext: str) -> str:
    """Decrypt a stored API key back to plaintext."""
    return decrypt_api_key(ciphertext)


def scrub_key_from_text(text: str, encrypted_api_key: str) -> str:
    """Redact a stored key's own plaintext value out of arbitrary text before it's shown or logged.

    Used on raw provider/network exception messages (api/api_keys.py's "Test" button,
    api/projects.py's preview chat and start-audio generation) before they reach the response
    body. Some providers (e.g. Google Gemini) put the API key directly in the request URL, and
    some HTTP client error messages include that full URL — without this, a raw exception can
    echo the key back to its own owner in a response body (browser devtools, a support
    screen-share, ...). Never raises: a key that fails to decrypt just means nothing gets redacted.
    """
    try:
        plaintext = reveal_api_key(encrypted_api_key)
    except Exception:
        return text
    if plaintext and plaintext in text:
        return text.replace(plaintext, "[REDACTED]")
    return text
