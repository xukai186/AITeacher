from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models import MediaAsset

MEDIA_ROOT = Path(__file__).resolve().parents[2] / "var" / "media"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_COPY_CHUNK_BYTES = 64 * 1024


class UploadTooLargeError(ValueError):
    pass


def _matches_content_type(header: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return header.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    return False


class MediaAssetService:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or MEDIA_ROOT

    def store(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        created_by: uuid.UUID,
        content_type: str,
        source: BinaryIO,
    ) -> MediaAsset:
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise ValueError("unsupported image content type")

        first_chunk = source.read(_COPY_CHUNK_BYTES)
        if not _matches_content_type(first_chunk[:16], content_type):
            raise ValueError("uploaded content does not match its image content type")

        asset_id = uuid.uuid4()
        directory = self._root / str(org_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / str(asset_id)
        total_bytes = 0
        try:
            with path.open("wb") as destination:
                chunk = first_chunk
                while chunk:
                    total_bytes += len(chunk)
                    if total_bytes > MAX_UPLOAD_BYTES:
                        raise UploadTooLargeError(
                            f"image upload exceeds {MAX_UPLOAD_BYTES} bytes"
                        )
                    destination.write(chunk)
                    chunk = source.read(_COPY_CHUNK_BYTES)
        except Exception:
            path.unlink(missing_ok=True)
            try:
                directory.rmdir()
            except OSError:
                pass
            raise

        asset = MediaAsset(
            id=asset_id,
            org_id=org_id,
            created_by=created_by,
            content_type=content_type,
            storage_path=str(path),
        )
        db.add(asset)
        return asset
