"""Flask application factory for the Tianshu Cup system."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, Response, request, send_from_directory

from backend.api import register_api
from backend.http import ApiError, json_response
from backend.workspace import DemoWorkspace

APP_VERSION = "4.0.0-tianshu-flask"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
ALLOWED_DEV_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


def create_app(
    config: dict[str, Any] | None = None,
    *,
    workspace: DemoWorkspace | None = None,
) -> Flask:
    """Build an isolated app instance for production, tests or local demos."""

    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        APP_VERSION=APP_VERSION,
        JSON_AS_ASCII=False,
        MAX_CONTENT_LENGTH=256 * 1024 * 1024,
    )
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False
    app.extensions["tianshu.workspace"] = workspace or DemoWorkspace()
    register_api(app)
    _register_error_handlers(app)
    _register_cors(app)
    _register_frontend(app)
    return app


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        payload: dict[str, Any] = {"detail": error.detail}
        if error.errors is not None:
            payload["errors"] = error.errors
        return json_response(payload, error.status_code)

    @app.errorhandler(404)
    def handle_not_found(_error):
        detail = "API endpoint not found" if request.path.startswith("/api/") else "页面不存在"
        return json_response({"detail": detail}, 404)

    @app.errorhandler(413)
    def handle_too_large(_error):
        return json_response({"detail": "上传内容超过系统允许的大小"}, 413)

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        app.logger.exception("Unhandled API error", exc_info=error)
        return json_response({"detail": "服务器内部错误，请查看服务日志"}, 500)


def _register_cors(app: Flask) -> None:
    @app.after_request
    def add_cors_headers(response: Response):
        origin = request.headers.get("Origin")
        if origin in ALLOWED_DEV_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
            response.headers.add("Vary", "Origin")
        return response


def _register_frontend(app: Flask) -> None:
    @app.get("/assets/<path:filename>")
    def frontend_asset(filename: str):
        return send_from_directory(FRONTEND_DIST / "assets", filename)

    @app.get("/")
    def frontend_index():
        if not (FRONTEND_DIST / "index.html").exists():
            return json_response(
                {"detail": "前端尚未构建，请在 frontend 目录运行 npm run build"}, 503
            )
        return send_from_directory(FRONTEND_DIST, "index.html")

    @app.get("/<path:path>")
    def frontend_fallback(path: str):
        if path.startswith("api/"):
            return json_response({"detail": "API endpoint not found"}, 404)
        return send_from_directory(FRONTEND_DIST, "index.html")
