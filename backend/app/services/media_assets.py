from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models import MediaAsset

MEDIA_ROOT = Path(__file__).resolve().parents[2] / "var" / "media"


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
        if not content_type.startswith("image/"):
            raise ValueError("only image uploads are supported")

        asset_id = uuid.uuid4()
        directory = self._root / str(org_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / str(asset_id)
        with path.open("wb") as destination:
            shutil.copyfileobj(source, destination)

        asset = MediaAsset(
            id=asset_id,
            org_id=org_id,
            created_by=created_by,
            content_type=content_type,
            storage_path=str(path),
        )
        db.add(asset)
        return asset
