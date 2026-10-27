from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask_client import TestClient

from tianshu_core.rag.config import PolicyRagSettings


class PolicyLibraryApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        root = Path(self._tmpdir.name)
        self.settings = PolicyRagSettings(
            policy_dir=root / "policies",
            index_path=root / "policy_index.json",
            chroma_path=root / "chroma",
            embedding_model=root / "embedding-model",
            backend="local",
        )
        self._settings_patch = patch(
            "backend.api.policy._rag_settings", return_value=self.settings
        )
        self._settings_patch.start()
        from backend.main import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._settings_patch.stop()
        self._tmpdir.cleanup()

    def test_uploaded_document_enters_library_and_search(self):
        response = self.client.post(
            "/api/rag/policies/upload",
            files={
                "files": (
                    "城市更新政策.txt",
                    "低效工业用地更新应优先开展权属核验和公共空间补足。",
                    "text/plain",
                )
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        documents = response.json()
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["name"], "城市更新政策.txt")
        self.assertIn("user_uploads", documents[0]["source"])

        detail = self.client.get(f"/api/rag/policies/{documents[0]['id']}")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertIn("权属核验", detail.json()["content"])

        search = self.client.get("/api/rag/search", params={"q": "工业用地更新", "limit": 3})
        self.assertEqual(search.status_code, 200, search.text)
        self.assertEqual(len(search.json()), 1)

    def test_rejects_unsupported_file(self):
        response = self.client.post(
            "/api/rag/policies/upload",
            files={"files": ("policy.json", "{}", "application/json")},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
