"""Tests for scrub_key_from_text (app/services/crypto_service.py) — redacts a stored key's own
plaintext value out of a raw provider/network exception message before it reaches a response
body. Some providers (e.g. Google Gemini) put the API key directly in the request URL, and some
HTTP client error messages include that full URL, so an unscrubbed exception can otherwise echo
the key back to its own owner."""

from app.services.crypto_service import scrub_key_from_text, store_api_key


def test_redacts_the_key_when_present_in_the_text() -> None:
    encrypted = store_api_key("AIzaSyD-super-secret-key")
    message = "Client error '400' for url 'https://api.example.com/v1?key=AIzaSyD-super-secret-key'"

    scrubbed = scrub_key_from_text(message, encrypted)

    assert "AIzaSyD-super-secret-key" not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_leaves_unrelated_text_unchanged() -> None:
    encrypted = store_api_key("AIzaSyD-super-secret-key")
    message = "Connection timed out after 30s"

    assert scrub_key_from_text(message, encrypted) == message


def test_never_raises_on_a_key_that_fails_to_decrypt() -> None:
    message = "some provider error"
    assert scrub_key_from_text(message, "not-a-valid-fernet-token") == message
