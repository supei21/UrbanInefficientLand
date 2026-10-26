from __future__ import annotations

from time import sleep

from flask import Blueprint

from backend.context import workspace_service
from backend.http import ApiError, ndjson_response, parse_body
from backend.schemas import ChatRequest
from tianshu_core.agent.events import AgentEvent
from tianshu_core.llm.client import get_model_settings, list_model_options
from tianshu_core.regeneration_chat import handle_regeneration_chat

chat_api = Blueprint("chat_api", __name__)


def _stream_text_chunks(text: str, size: int = 24) -> list[str]:
    chunks: list[str] = []
    current = ""
    for char in text:
        current += char
        if len(current) >= size or char in {"\n", "。", "；", "，"}:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


@chat_api.post("/chat/stream")
def stream_chat():
    payload = parse_body(ChatRequest)
    try:
        get_model_settings(payload.model_id)
    except KeyError as exc:
        raise ApiError(422, str(exc)) from exc
    model_option = next(
        (item for item in list_model_options() if item["id"] == payload.model_id), None
    )
    if model_option is None or not model_option["ready"]:
        raise ApiError(422, "所选模型尚未完成配置")

    workspace = workspace_service()
    blocks_snapshot = list(workspace.blocks)

    def produce(publish):
        def publish_event(event: AgentEvent) -> None:
            publish({"type": "process", "event": event.model_dump(mode="json")})

        result = handle_regeneration_chat(
            payload.query,
            blocks_snapshot,
            analysis_provider=workspace.get_latest_regeneration_payload,
            analysis_runner=workspace.run_regeneration_analysis,
            event_callback=publish_event,
        )
        result_payload = result.model_dump(mode="json")
        result_payload["model_id"] = payload.model_id
        result_payload["model_name"] = model_option["label"]
        for chunk in _stream_text_chunks(str(result_payload.get("response") or "")):
            publish({"type": "answer_delta", "content": chunk})
            # 给浏览器留出绘制窗口，使本地规则回答也呈现可观察的流式反馈。
            sleep(0.018)
        publish({"type": "result", "result": result_payload})

    return ndjson_response(produce, error_prefix="分析失败")
