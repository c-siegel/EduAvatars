"""
Voice-Message Uploads

The shared validation for a recorded voice message, used by both the public chat's and the
configurator preview's transcribe routes.
"""

from fastapi import UploadFile

from app.core.error_codes import ErrorCode
from app.core.errors import DomainError

MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — individual chat voice messages are short
ALLOWED_AUDIO_CONTENT_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"}


class UnsupportedAudioFormat(DomainError):
    status_code = 400
    detail = ErrorCode.UNSUPPORTED_AUDIO_FORMAT


class AudioFileTooLarge(DomainError):
    status_code = 400
    detail = ErrorCode.AUDIO_FILE_TOO_LARGE


def read_audio_upload(audio: UploadFile) -> bytes:
    """Check the upload's content type and size, and return its bytes."""
    if audio.content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise UnsupportedAudioFormat()
    content = audio.file.read(MAX_AUDIO_UPLOAD_BYTES + 1)
    if len(content) > MAX_AUDIO_UPLOAD_BYTES:
        raise AudioFileTooLarge()
    return content
