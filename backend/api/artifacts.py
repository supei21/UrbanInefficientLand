from __future__ import annotations

from flask import Blueprint, Response, send_file

from backend.context import workspace_service
from backend.http import ApiError, json_response

artifacts_api = Blueprint("artifacts_api", __name__)


@artifacts_api.get("/artifacts")
def list_artifacts():
    return json_response(workspace_service().list_artifacts())


@artifacts_api.get("/artifacts/<artifact_id>")
def get_artifact(artifact_id: str):
    artifact = workspace_service().get_artifact_detail(artifact_id)
    if artifact is None:
        raise ApiError(404, "成果文件不存在")
    return json_response(artifact)


def _artifact_response(artifact_id: str, *, download: bool):
    artifact = workspace_service().get_artifact(artifact_id)
    if artifact is None:
        raise ApiError(404, "成果文件不存在")
    if artifact.file_path is not None:
        return send_file(
            artifact.file_path,
            mimetype=artifact.summary.mime,
            as_attachment=download,
            download_name=artifact.summary.name,
        )
    if artifact.content is None:
        raise ApiError(404, "成果文件内容不存在")
    response = Response(artifact.content, mimetype=artifact.summary.mime)
    disposition = "attachment" if download else "inline"
    response.headers["Content-Disposition"] = f'{disposition}; filename="{artifact.summary.name}"'
    return response


@artifacts_api.get("/artifacts/<artifact_id>/preview")
def preview_artifact(artifact_id: str):
    return _artifact_response(artifact_id, download=False)


@artifacts_api.get("/artifacts/<artifact_id>/download")
def download_artifact(artifact_id: str):
    return _artifact_response(artifact_id, download=True)
