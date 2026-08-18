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
