from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from werkzeug.datastructures import FileStorage

from tianshu_core.paths import UPLOADS_DIR
from tianshu_core.spatial import MAX_UPLOAD_BYTES

UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024


class UploadTooLargeError(ValueError):
    pass


def persist_upload(file: FileStorage, original_name: str) -> tuple[Path, int]:
    """Stream a Werkzeug upload without loading large spatial files into memory."""

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(original_name).name or "uploaded-data.zip"
    target = UPLOADS_DIR / f"{uuid4().hex}_{safe_name}"
    total = 0
    try:
        with target.open("wb") as output:
            while chunk := file.stream.read(UPLOAD_CHUNK_SIZE):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
                    raise UploadTooLargeError(f"上传文件不能超过{limit_mb}MB")
                output.write(chunk)
        return target, total
    except Exception:
        target.unlink(missing_ok=True)
        raise
