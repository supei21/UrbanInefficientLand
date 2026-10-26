from __future__ import annotations

import json
import zipfile
from pathlib import Path

from flask import Blueprint, request

from backend.context import workspace_service
from backend.http import ApiError, integer_query, json_response
from backend.uploads import UploadTooLargeError, persist_upload
from tianshu_core.io import parse_csv, parse_json
from tianshu_core.spatial import (
    read_arcgis_feature_set,
    read_landscape_boundary_from_constraint_zip,
    read_shapefile_zip_path,
)

data_api = Blueprint("data_api", __name__)


def _required_file(field: str = "file"):
    file = request.files.get(field)
    if file is None or not file.filename:
        raise ApiError(400, "请选择需要上传的文件")
    return file


@data_api.get("/dataset")
def get_dataset():
    offset = integer_query("offset", 0, minimum=0, maximum=10_000_000)
    limit = integer_query("limit", 50, minimum=1, maximum=500)
    query = request.args.get("q") or None
    if query and len(query) > 120:
        raise ApiError(422, "查询内容不能超过120个字符")
    return json_response(
        workspace_service().dataset_payload(offset=offset, limit=limit, query=query)
    )


@data_api.get("/candidates")
def get_candidate_parcels():
    return json_response(workspace_service().candidate_parcels())


@data_api.post("/datasets/upload")
def upload_dataset():
    file = _required_file()
    name = file.filename or "uploaded-data"
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix not in {"json", "csv", "zip"}:
        raise ApiError(400, "当前Demo支持JSON、CSV或SHP ZIP")
    workspace = workspace_service()
    try:
        if suffix == "zip":
            upload_path, _ = persist_upload(file, name)
            try:
                dataset = read_shapefile_zip_path(name, upload_path)
            except Exception:
                upload_path.unlink(missing_ok=True)
                raise
            workspace.set_spatial_dataset(dataset, upload_path)
            return json_response(workspace.summary())

        content = file.read()
        if suffix == "json":
            parsed = json.loads(content.decode("utf-8-sig"))
            if (
                isinstance(parsed, dict)
                and isinstance(parsed.get("features"), list)
                and parsed.get("geometryType")
            ):
                dataset = read_arcgis_feature_set(name, content)
                workspace.set_spatial_dataset(dataset, dataset.source_path)
                return json_response(workspace.summary())
            blocks = parse_json(content)
        else:
            blocks = parse_csv(content)
    except UploadTooLargeError as exc:
        raise ApiError(413, str(exc)) from exc
    except (ValueError, TypeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise ApiError(422, f"数据解析失败：{exc}") from exc
    mime = "application/json" if suffix == "json" else "text/csv"
    workspace.set_dataset(name, blocks, content, mime)
    return json_response(workspace.summary())


@data_api.post("/constraints/upload")
def upload_constraint_dataset():
    file = _required_file()
    name = file.filename or "constraint-data"
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix not in {"zip", "json", "geojson"}:
        raise ApiError(400, "约束数据当前支持SHP ZIP、JSON或GeoJSON")
    upload_path: Path | None = None
    try:
        upload_path, _ = persist_upload(file, name)
        landscape_boundary = (
            read_landscape_boundary_from_constraint_zip(name, upload_path)
            if suffix == "zip"
            else None
        )
        workspace_service().set_constraint_dataset(name, upload_path, landscape_boundary)
    except UploadTooLargeError as exc:
        raise ApiError(413, str(exc)) from exc
    except (ValueError, TypeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        if upload_path is not None:
            upload_path.unlink(missing_ok=True)
        raise ApiError(422, f"约束数据解析失败：{exc}") from exc
    return json_response(workspace_service().summary())
