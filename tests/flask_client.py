"""Small compatibility adapter used while preserving the existing API test intent."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from flask import Flask
from werkzeug.test import TestResponse


class ResponseAdapter:
    def __init__(self, response: TestResponse) -> None:
        self._response = response

    def json(self) -> Any:
        return self._response.get_json()

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self):
        return self._response.headers

    @property
    def content(self) -> bytes:
        return self._response.data

    @property
    def text(self) -> str:
        return self._response.get_data(as_text=True)

    def close(self) -> None:
        self._response.close()


class TestClient:
    def __init__(self, app: Flask) -> None:
        self._client = app.test_client()

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> ResponseAdapter:
        return ResponseAdapter(self._client.get(path, query_string=params))

    def post(
        self,
        path: str,
        *,
        json: Any = None,
        files: dict[str, tuple[str, Any, str]] | None = None,
    ) -> ResponseAdapter:
        data = None
        content_type = None
        if files:
            data = {}
            for field, (name, content, mime) in files.items():
                raw = content.encode("utf-8") if isinstance(content, str) else content
                data[field] = (BytesIO(raw), name, mime)
            content_type = "multipart/form-data"
        response = self._client.post(path, json=json, data=data, content_type=content_type)
        return ResponseAdapter(response)

    def delete(self, path: str) -> ResponseAdapter:
        return ResponseAdapter(self._client.delete(path))
