from __future__ import annotations

import unittest

from tianshu_core.regeneration import analyze_regeneration


class RegenerationAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.blocks = [
            {
                "block_id": "A",
                "block_name": "老旧低活力片区",
                "poi_density": 1,
                "poi_commercial": 1,
                "poi_public_service": 2,
                "poi_transport": 8,
                "poi_industrial": 1,
                "pop_density": 100,
                "road_density": 7,
                "built_area_ratio": 0.25,
                "tree_cover_ratio": 0.05,
                "vacancy_rate": 0.7,
                "building_age": 45,
            },
            {
                "block_id": "B",
                "block_name": "成熟活力片区",
                "poi_density": 80,
                "poi_commercial": 50,
                "poi_public_service": 50,
                "poi_transport": 30,
                "poi_industrial": 20,
                "pop_density": 12000,
                "road_density": 12,
                "built_area_ratio": 0.85,
                "tree_cover_ratio": 0.30,
                "vacancy_rate": 0.05,
                "building_age": 8,
            },
            {
                "block_id": "C",
                "block_name": "生态约束片区",
                "poi_density": 3,
                "road_density": 2,
                "tree_cover_ratio": 0.8,
                "ecological_redline": True,
            },
        ]

    def test_analysis_returns_ranked_explainable_decisions(self) -> None:
        result = analyze_regeneration(self.blocks)
        self.assertEqual(result["summary"]["total"], 3)
        self.assertEqual([item["rank"] for item in result["decisions"]], [1, 2, 3])
        for item in result["decisions"]:
            self.assertGreaterEqual(item["inefficiency_score"], 0)
            self.assertLessEqual(item["inefficiency_score"], 100)
            self.assertGreaterEqual(item["regeneration_potential"], 0)
            self.assertLessEqual(item["regeneration_potential"], 100)
            self.assertTrue(item["scenario_actions"])
            self.assertTrue(item["key_evidence"])

    def test_hard_constraint_routes_to_ecological_restoration(self) -> None:
        result = analyze_regeneration(self.blocks)
        by_id = {item["block_id"]: item for item in result["decisions"]}
        self.assertEqual(by_id["C"]["regeneration_scenario"], "生态修复")

    def test_empty_dataset_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "没有可分析地块"):
            analyze_regeneration([])


if __name__ == "__main__":
    unittest.main()
