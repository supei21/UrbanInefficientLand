"""HTTP boundary helpers shared by Flask blueprints.

The domain layer deliberately knows nothing about Flask.  This module is the
single translation boundary for request validation, JSON serialisation and
API errors.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, TypeVar

from flask import Response, jsonify, request, stream_with_context
from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)
_STREAM_END = object()


class ApiError(Exception):
    """An expected client-facing error with an explicit HTTP status."""

    def __init__(self, status_code: int, detail: str, *, errors: Any = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.errors = errors


def parse_body(model_type: type[ModelT]) -> ModelT:
    """Validate a JSON request once, at the transport boundary."""

    try:
        return model_type.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        raise ApiError(422, "请求参数校验失败", errors=exc.errors()) from exc


def as_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: as_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def json_response(value: Any, status: int = 200) -> tuple[Response, int]:
    return jsonify(as_jsonable(value)), status


def integer_query(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ApiError(422, f"参数 {name} 必须为整数") from exc
    if not minimum <= value <= maximum:
        raise ApiError(422, f"参数 {name} 必须在 {minimum} 到 {maximum} 之间")
    return value


def ndjson_response(
    producer: Callable[[Callable[[dict[str, Any]], None]], None],
    *,
    error_prefix: str,
) -> Response:
    """Run blocking domain work in a thread and expose progress as NDJSON."""

    event_queue: Queue[object] = Queue()

    def publish(packet: dict[str, Any]) -> None:
        event_queue.put(as_jsonable(packet))

    def run() -> None:
        try:
            producer(publish)
        except Exception as exc:  # The stream already started; report in-band.
            publish({"type": "error", "message": f"{error_prefix}：{exc}"})
        finally:
            event_queue.put(_STREAM_END)

    Thread(target=run, daemon=True).start()

    @stream_with_context
    def generate() -> Iterator[str]:
        import json

        while True:
            item = event_queue.get()
            if item is _STREAM_END:
                break
            yield json.dumps(item, ensure_ascii=False) + "\n"

    response = Response(generate(), mimetype="application/x-ndjson")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response
