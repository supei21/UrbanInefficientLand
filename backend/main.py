"""WSGI entry point kept intentionally thin."""

from backend.app import create_app
from backend.workspace import DemoWorkspace

workspace = DemoWorkspace()
app = create_app(workspace=workspace)
