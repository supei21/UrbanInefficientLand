from __future__ import annotations

from flask import Blueprint, current_app

from backend.context import workspace_service
from backend.http import ApiError, json_response, parse_body
from backend.schemas import CreateUserModelResponse, UserModelInput, UserModelOutput
from tianshu_core.llm.user_models import (
    UserModelConflictError,
    add_user_model,
    delete_user_model,
)

system_api = Blueprint("system_api", __name__)


@system_api.get("/health")
def health():
    summary = workspace_service().summary()
    return json_response(
        {
            "status": "ok",
            "version": current_app.config["APP_VERSION"],
            "model_ready": summary.model_ready,
            "block_count": summary.block_count,
        }
    )


@system_api.get("/workspace")
def get_workspace():
    return json_response(workspace_service().summary())


@system_api.post("/workspace/reset")
def reset_workspace():
    workspace = workspace_service()
    workspace.reset()
    return json_response(workspace.summary())


@system_api.post("/models")
def create_user_model():
    payload = parse_body(UserModelInput)
    try:
        record = add_user_model(payload.label, payload.model, payload.base_url, payload.api_key)
    except UserModelConflictError as exc:
        raise ApiError(409, str(exc)) from exc
    response = CreateUserModelResponse(
        model=UserModelOutput(
            id=record["id"],
            label=record["label"],
            model=record["model"],
            base_url=record["base_url"],
            created_at=record["created_at"],
            api_key_masked=f"••••{record['api_key'][-4:]}",
        ),
        workspace=workspace_service().summary(),
    )
    return json_response(response)


@system_api.delete("/models/<model_id>")
def remove_user_model(model_id: str):
    if not model_id.startswith("custom-"):
        raise ApiError(400, "只能删除自定义模型")
    if not delete_user_model(model_id):
        raise ApiError(404, "自定义模型不存在")
    return json_response(workspace_service().summary())
