"""HTTP route registration.

Blueprints are grouped by user capability so each adapter stays small and
changes in one feature do not force unrelated features to move together.
"""

from __future__ import annotations

from flask import Flask

from backend.api.analysis import analysis_api
from backend.api.artifacts import artifacts_api
from backend.api.chat import chat_api
from backend.api.data import data_api
from backend.api.policy import policy_api
from backend.api.system import system_api


def register_api(app: Flask) -> None:
    for blueprint in (
        system_api,
        data_api,
        analysis_api,
        policy_api,
        artifacts_api,
        chat_api,
    ):
        app.register_blueprint(blueprint, url_prefix="/api")
