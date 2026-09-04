"""
Where an athlete's picture is kept.

A separate module from the settings routes because deleting an account has to
remove the picture too, and the account routes cannot import the settings
routes -- those already import the account routes for the session dependency,
and the pair would not load.

Pictures are files rather than database rows. They are the one thing here that
is not a number, they do not belong in a backup of the training data, and a
file is trivially inspectable if someone wonders what is stored about them.
"""
import os

from backend.app.core.config import settings

AVATAR_DIR = os.getenv("AVATAR_DIR", os.path.join(settings.DATA_DIR, "avatars"))

# The browser scales the picture to a small square before uploading, so
# anything approaching this is not a photograph of a person: it is a mistake,
# or an attempt at one.
MAX_AVATAR_BYTES = 1_048_576

# Identified by content, never by the name the upload arrived with. A file
# called avatar.png is not a PNG because it says so.
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
)

EXTENSIONS = ("png", "jpg", "webp")

MEDIA_TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}


def sniff(data: bytes):
    """The image's real type as (extension, media type), or None if unusable."""
    for signature, extension, media_type in IMAGE_SIGNATURES:
        if data.startswith(signature):
            return extension, media_type
    # WebP is a RIFF container with a WEBP tag four bytes in.
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def avatar_path(user_id: str):
    """The stored picture for an account, or None."""
    for extension in EXTENSIONS:
        candidate = os.path.join(AVATAR_DIR, f"{user_id}.{extension}")
        if os.path.exists(candidate):
            return candidate
    return None


def media_type_of(path: str) -> str:
    return MEDIA_TYPES.get(path.rsplit(".", 1)[-1], "application/octet-stream")


def store(user_id: str, data: bytes, extension: str) -> str:
    os.makedirs(AVATAR_DIR, exist_ok=True)
    # One picture per account. The old one goes whatever format it was in, so a
    # stale JPEG cannot linger behind a newly uploaded PNG.
    remove_avatar(user_id)
    path = os.path.join(AVATAR_DIR, f"{user_id}.{extension}")
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def remove_avatar(user_id: str) -> None:
    """Called when an account is deleted, so nothing of it is left behind."""
    for extension in EXTENSIONS:
        candidate = os.path.join(AVATAR_DIR, f"{user_id}.{extension}")
        if os.path.exists(candidate):
            try:
                os.remove(candidate)
            except OSError:
                pass
