"""Dependency accessors for request-scoped Flask adapters."""

from __future__ import annotations

from flask import current_app

from backend.workspace import DemoWorkspace


def workspace_service() -> DemoWorkspace:
    """Return the application-owned workspace without a module-level import cycle."""

    return current_app.extensions["tianshu.workspace"]
