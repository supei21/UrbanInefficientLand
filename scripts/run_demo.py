"""Run the built Vue frontend and Flask API on one local port."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


if __name__ == "__main__":
    from backend.main import app

    app.run(host="127.0.0.1", port=8000, debug=False, threaded=True)
