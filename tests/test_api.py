from __future__ import annotations

import json
import unittest

from flask_client import TestClient
from test_spatial import make_shapefile_zip

from backend.main import app, workspace
from tianshu_core.models import BlockDecision
from tianshu_core.paths import SAMPLE_DATA_FILE


class ApiTest(unittest.TestCase):
    def setUp(self):
        workspace.reset()
        self.client = TestClient(app)
        self.expected_block_count = len(workspace.blocks)
        self.first_block_id = str(workspace.blocks[0]["block_id"])

    def test_workspace_uses_sample_data(self):
        response = self.client.get("/api/workspace")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["block_count"], self.expected_block_count)
        self.assertIn("dataset_name", payload)

    def test_dataset_endpoint_search_and_pagination(self):
        response = self.client.get("/api/dataset")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["block_count"], self.expected_block_count)
        self.assertEqual(payload["matched_count"], self.expected_block_count)
        self.assertEqual(len(payload["blocks"]), min(50, self.expected_block_count))
        self.assertEqual(payload["has_more"], self.expected_block_count > 50)

        page = self.client.get("/api/dataset", params={"offset": 0, "limit": 2}).json()
        self.assertEqual(len(page["blocks"]), 2)
        self.assertTrue(page["has_more"])
        tail = self.client.get(
            "/api/dataset",
            params={"offset": self.expected_block_count - 1, "limit": 2},
        ).json()
        self.assertEqual(len(tail["blocks"]), 1)
        self.assertFalse(tail["has_more"])

        found = self.client.get("/api/dataset", params={"q": self.first_block_id}).json()
        self.assertEqual(found["matched_count"], 1)
        self.assertEqual(found["blocks"][0]["block_id"], self.first_block_id)
        self.assertEqual(found["block_count"], self.expected_block_count)

        none = self.client.get("/api/dataset", params={"q": "不存在的街区"}).json()
        self.assertEqual(none["matched_count"], 0)
        self.assertEqual(none["blocks"], [])
        self.assertFalse(none["has_more"])

    def test_upload_json_dataset(self):
        response = self.client.post(
            "/api/datasets/upload",
            files={"file": ("blocks.json", SAMPLE_DATA_FILE.read_bytes(), "application/json")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["block_count"], self.expected_block_count)
        self.assertEqual(response.json()["artifacts"][0]["kind"], "dataset")

    def test_upload_shapefile_zip_dataset(self):
        response = self.client.post(
            "/api/datasets/upload",
            files={"file": ("blocks.shp.zip", make_shapefile_zip(), "application/zip")},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["block_count"], 2)
        self.assertTrue(payload["has_spatial_data"])
        self.assertEqual(payload["artifacts"][0]["kind"], "spatial")
        artifact_id = payload["artifacts"][0]["id"]
        stored = workspace.get_artifact(artifact_id)
        self.assertIsNotNone(stored)
        self.assertIsNotNone(stored.file_path if stored else None)
        self.assertTrue(stored.file_path.exists() if stored and stored.file_path else False)
        detail = self.client.get(f"/api/artifacts/{artifact_id}").json()
        self.assertEqual(detail["preview"]["spatial"]["type"], "FeatureCollection")
        download = self.client.get(f"/api/artifacts/{artifact_id}/download")
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download.content.startswith(b"PK"))
        download.close()

        replacement = self.client.post(
            "/api/datasets/upload",
            files={"file": ("replacement.shp.zip", make_shapefile_zip(), "application/zip")},
        ).json()
        self.assertEqual(len(replacement["artifacts"]), 1)
        self.assertFalse(stored.file_path.exists() if stored and stored.file_path else True)

    def test_upload_constraint_dataset_does_not_replace_blocks(self):
        response = self.client.post(
            "/api/constraints/upload",
            files={"file": ("三线约束数据.zip", make_shapefile_zip(), "application/zip")},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["block_count"], self.expected_block_count)
        self.assertFalse(payload["has_spatial_data"])
        self.assertTrue(payload["constraint_dataset"]["loaded"])
        self.assertGreaterEqual(payload["constraint_dataset"]["layer_count"], 1)
        self.assertEqual(payload["artifacts"], [])

    def test_upload_policy_and_generate_pdf_report(self):
        upload = self.client.post(
            "/api/policies/upload",
            files={
                "files": (
                    "policy.txt",
                    "推进低效空间再生时，应避让生态保护红线和永久基本农田。",
                    "text/plain",
                )
            },
        )
        self.assertEqual(upload.status_code, 200)
        self.assertGreaterEqual(len(upload.json()["policy_documents"]), 1)

        workspace.add_analysis(
            {
                "response": "测试分析",
                "block_records": [],
                "decisions": [
                    BlockDecision(
                        block_id=self.first_block_id,
                        block_name="测试街区",
                        inside_boundary=False,
                        decision="一级优先调入",
                        overall_suitability=88,
                        development_probability=90,
                        planning_match=86,
                        constraint_cost=8,
                        dynamic_score=89,
                        confidence=0.91,
                        constraint_status="通过",
                        key_reasons=["建设基础较好"],
                        risks=[],
                        missing_information=[],
                        manual_review_required=False,
                        recommendation="建议纳入优先复核",
                        rule_version="test",
                    ).model_dump(mode="json")
                ],
            }
        )

        report = self.client.post("/api/reports/policy-pdf", json={"model_id": "local-rules"})
        self.assertEqual(report.status_code, 200)
        payload = report.json()
        self.assertEqual(payload["kind"], "report")
        self.assertEqual(payload["mime"], "application/pdf")
        artifacts = self.client.get("/api/artifacts").json()
        self.assertTrue(any(item["name"].endswith(".docx") for item in artifacts))
        download = self.client.get(f"/api/artifacts/{payload['id']}/download")
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download.content.startswith(b"%PDF"))
        download.close()
        preview = self.client.get(f"/api/artifacts/{payload['id']}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "application/pdf")
        self.assertIn("inline", preview.headers["content-disposition"])
        preview.close()
        detail = self.client.get(f"/api/artifacts/{payload['id']}").json()
        self.assertIn("candidate_blocks", detail["preview"]["evidence"])

    def test_reference_policy_pdf_preview(self):
        response = self.client.get("/api/policies/reference-pdf/preview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        response.close()

    def test_rag_policy_library_endpoints(self):
        listing = self.client.get("/api/rag/policies")
        self.assertEqual(listing.status_code, 200)
        documents = listing.json()
        self.assertGreaterEqual(len(documents), 1)

        detail = self.client.get(f"/api/rag/policies/{documents[0]['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertGreater(detail.json()["text_length"], 0)

        search = self.client.get("/api/rag/search", params={"q": "低效空间 再生更新", "limit": 3})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(len(search.json()), 3)

    def test_stream_returns_process_and_result_packets(self):
        response = self.client.post(
            "/api/chat/stream",
            json={"query": "介绍系统操作流程", "model_id": "local-rules"},
        )

        self.assertEqual(response.status_code, 200)
        packets = [json.loads(line) for line in response.text.splitlines() if line]
        self.assertEqual(packets[0]["type"], "process")
        self.assertEqual(packets[-1]["type"], "result")
        streamed_answer = "".join(
            packet["content"] for packet in packets if packet["type"] == "answer_delta"
        )
        self.assertEqual(streamed_answer, packets[-1]["result"]["response"])
        self.assertIn("低效识别", packets[-1]["result"]["response"])
        self.assertEqual(packets[-1]["result"]["model_id"], "local-rules")

    def test_workspace_returns_safe_model_catalog(self):
        payload = self.client.get("/api/workspace").json()
        self.assertIn("default_model_id", payload)
        self.assertTrue(any(item["id"] == "local-rules" for item in payload["models"]))
        self.assertNotIn("api_key", json.dumps(payload))

    def test_unknown_model_is_rejected(self):
        response = self.client.post(
            "/api/chat/stream",
            json={"query": "测试问题", "model_id": "not-configured"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
