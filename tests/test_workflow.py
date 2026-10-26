from __future__ import annotations

import json
import unittest
from copy import deepcopy

from tianshu_core.config import load_config
from tianshu_core.io import parse_json
from tianshu_core.paths import SAMPLE_DATA_FILE
from tianshu_core.workflow.graph import run_workflow


class WorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_workflow(
            parse_json(SAMPLE_DATA_FILE.read_bytes()),
            include_ai_explanations=False,
        )

    def test_count(self):
        self.assertEqual(self.result["summary"]["total"], 3)

    def test_hard_constraint_never_included(self):
        decisions = {item["block_id"]: item for item in self.result["decisions"]}
        self.assertEqual(decisions["WH2025_DEMO002"]["decision"], "人工复核")

    def test_high_risk_low_suitability_excluded(self):
        decisions = {item["block_id"]: item for item in self.result["decisions"]}
        self.assertEqual(decisions["WH2025_DEMO003"]["decision"], "建议调出")

    def test_json_serializable(self):
        json.dumps(self.result, ensure_ascii=False)

    def test_dynamic_adaptation_fields_and_ranks(self):
        decisions = self.result["decisions"]
        self.assertEqual(sorted(item["rank_city"] for item in decisions), [1, 2, 3])
        for item in decisions:
            self.assertGreaterEqual(item["dynamic_score"], 0)
            self.assertLessEqual(item["dynamic_score"], 100)
            self.assertIn("development_probability", item)
            self.assertIn("planning_match", item)
            self.assertIn("constraint_cost", item)
            self.assertTrue(item["key_drivers"])

    def test_summary_contains_top_candidates(self):
        self.assertTrue(self.result["summary"]["top_candidate_ids"])
        self.assertIn("dynamic_score_average", self.result["summary"])
        self.assertIn("policy_compliance_counts", self.result["summary"])

    def test_llm_explanations_can_be_disabled(self):
        self.assertTrue(all(item["ai_explanation"] is None for item in self.result["decisions"]))

    def test_development_potential_selects_top_five_and_twenty_percent(self):
        blocks = [
            {
                "block_id": f"P{index:03d}",
                "block_name": "测试区",
                "inside_boundary": False,
                "development_potential": index / 99,
                "sec_prob": index / 99,
                "ter_prob": 0.2,
                "tra_prob": 0.1,
                "poi_density": 10,
                "road_density": 5,
                "construction_ratio": 0.3,
                "ecological_redline": False,
                "permanent_farmland": False,
                "prohibited_disaster_zone": False,
            }
            for index in range(100)
        ]
        config = deepcopy(load_config())
        config["trained_model"]["enabled"] = False
        config["policy_rag"]["enabled"] = False
        result = run_workflow(blocks, config, include_ai_explanations=False)
        counts = result["summary"]["decision_counts"]
        self.assertEqual(counts["一级优先调入"], 5)
        self.assertEqual(counts["二级优先调入"], 15)
        self.assertEqual(
            result["summary"]["trained_model"]["source"],
            "uploaded_development_potential",
        )

    def test_boundary_position_and_dev_score_control_adjustment_direction(self):
        blocks = [
            {
                "block_id": block_id,
                "block_name": "边界规则测试",
                "inside_boundary": inside,
                "development_potential": dev_score,
                "boundary_overlap_ratio": overlap,
                "poi_density": 10,
                "road_density": 5,
                "construction_ratio": 0.3,
                "ecological_redline": False,
                "permanent_farmland": False,
                "prohibited_disaster_zone": False,
            }
            for block_id, inside, dev_score, overlap in (
                ("OUT_HIGH", False, 0.90, 0.0),
                ("OUT_LOW", False, 0.20, 0.0),
                ("PARTIAL_HIGH", False, 0.99, 0.2),
                ("IN_HIGH", True, 0.95, 1.0),
                ("IN_LOW", True, 0.10, 1.0),
            )
        ]
        config = deepcopy(load_config())
        config["trained_model"]["enabled"] = False
        config["policy_rag"]["enabled"] = False
        result = run_workflow(blocks, config, include_ai_explanations=False)
        decisions = {item["block_id"]: item for item in result["decisions"]}

        self.assertIn(decisions["OUT_HIGH"]["decision"], {"一级优先调入", "二级优先调入"})
        self.assertNotEqual(decisions["OUT_LOW"]["decision"], "建议调出")
        self.assertNotIn(decisions["PARTIAL_HIGH"]["decision"], {"一级优先调入", "二级优先调入"})
        self.assertNotIn(decisions["IN_HIGH"]["decision"], {"一级优先调入", "二级优先调入"})
        self.assertEqual(decisions["IN_LOW"]["decision"], "建议调出")
        self.assertTrue(
            all(
                not item["inside_boundary"]
                for item in result["decisions"]
                if item["decision"] in {"一级优先调入", "二级优先调入"}
            )
        )
        self.assertTrue(
            all(
                item["inside_boundary"]
                for item in result["decisions"]
                if item["decision"] == "建议调出"
            )
        )


if __name__ == "__main__":
    unittest.main()
