from __future__ import annotations

import unittest
from unittest.mock import patch

from tianshu_core.regeneration import _scenario, analyze_regeneration


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
                "sec_prob": 0.8,
                "ter_prob": 0.5,
                "tra_prob": 0.2,
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
                "sec_prob": 0.2,
                "ter_prob": 0.4,
                "tra_prob": 0.1,
            },
            {
                "block_id": "C",
                "block_name": "生态约束片区",
                "poi_density": 3,
                "road_density": 2,
                "tree_cover_ratio": 0.8,
                "ecological_redline": True,
                "sec_prob": 0.9,
                "ter_prob": 0.9,
                "tra_prob": 0.9,
            },
        ]

    @staticmethod
    def _levels_for(levels: dict[str, str]):
        def evaluate(blocks):
            return [
                {
                    "source_index": index,
                    "inefficiency_score": 70.0 if block["block_id"] == "A" else 62.0,
                    "inefficiency_level": levels[block["block_id"]],
                    "inefficiency_dimensions": {"土地利用不足": 70.0},
                    "dominant_problem": "土地利用不足",
                    "screening_status": "候选-可进一步筛选",
                    "data_coverage": 1.0,
                    "manual_review_required": False,
                    "key_evidence": ["土地利用不足 70.0"],
                }
                for index, block in enumerate(blocks)
            ]

        return evaluate

    def test_only_high_and_obvious_are_scored_and_ranked(self) -> None:
        self.blocks[2].update(
            poi_commercial=1000,
            poi_transport=1000,
            poi_industrial=1000,
            pop_density=100000,
            road_density=1000,
            built_area_ratio=1.0,
        )
        levels = {"A": "高度低效", "B": "明显低效", "C": "疑似低效"}
        with patch("tianshu_core.regeneration.evaluate_low_efficiency", self._levels_for(levels)):
            result = analyze_regeneration(self.blocks)
            without_suspected = analyze_regeneration(self.blocks[:2])

        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(result["summary"]["candidate_count"], 2)
        self.assertEqual(
            result["summary"]["inefficiency_level_counts"],
            {
                "高度低效": 1,
                "明显低效": 1,
            },
        )
        self.assertEqual({item["block_id"] for item in result["decisions"]}, {"A", "B"})
        self.assertEqual([item["rank"] for item in result["decisions"]], [1, 2])
        potentials = {
            item["block_id"]: item["regeneration_potential"] for item in result["decisions"]
        }
        comparison = {
            item["block_id"]: item["regeneration_potential"]
            for item in without_suspected["decisions"]
        }
        self.assertNotEqual(potentials, comparison)
        self.assertEqual(potentials["A"], 50.0)
        self.assertEqual(comparison["A"], 100.0)
        self.assertEqual(result["method"]["potential_reference_count"], 3)
        by_id = {item["block_id"]: item for item in result["decisions"]}
        self.assertEqual(by_id["A"]["dev_score"], 0.5)
        self.assertEqual(by_id["A"]["potential_level"], "中")
        self.assertEqual(by_id["A"]["dev_type"], "第二产业、第三产业、交通（复合）")
        for item in result["decisions"]:
            self.assertGreaterEqual(item["inefficiency_score"], 0)
            self.assertLessEqual(item["inefficiency_score"], 100)
            self.assertGreaterEqual(item["regeneration_potential"], 0)
            self.assertLessEqual(item["regeneration_potential"], 100)
            self.assertTrue(item["scenario_actions"])
            self.assertTrue(item["key_evidence"])

    def test_hard_constraint_routes_to_ecological_restoration(self) -> None:
        levels = {"A": "高度低效", "B": "明显低效", "C": "高度低效"}
        with patch("tianshu_core.regeneration.evaluate_low_efficiency", self._levels_for(levels)):
            result = analyze_regeneration(self.blocks)
        by_id = {item["block_id"]: item for item in result["decisions"]}
        self.assertEqual(by_id["C"]["regeneration_scenario"], "生态修复或储备")
        self.assertEqual(by_id["C"]["scenario_subtype"], "生态修复")
        self.assertIn("生态保护红线", by_id["C"]["constraint_reasons"])

    def test_report_four_scenarios_include_threshold_boundary(self) -> None:
        cases = (
            ("高度低效", 50.0, "优先更新", None),
            ("明显低效", 50.0, "提质改善", None),
            ("高度低效", 49.99, "生态修复或储备", "储备"),
            ("明显低效", 49.99, "持续观察", None),
        )
        for level, potential, expected, subtype in cases:
            with self.subTest(level=level, potential=potential):
                scenario, actual_subtype, reason = _scenario(level, potential, [], 50)
                self.assertEqual((scenario, actual_subtype), (expected, subtype))
                self.assertTrue(reason)

    def test_missing_xgboost_probabilities_are_reported(self) -> None:
        self.blocks[0].pop("sec_prob")
        levels = {"A": "高度低效", "B": "明显低效", "C": "疑似低效"}
        with (
            patch("tianshu_core.regeneration.evaluate_low_efficiency", self._levels_for(levels)),
            self.assertRaisesRegex(ValueError, "sec_prob"),
        ):
            analyze_regeneration(self.blocks)

    def test_no_high_or_obvious_blocks_returns_empty_analysis(self) -> None:
        result = analyze_regeneration(self.blocks)
        self.assertEqual(result["decisions"], [])
        self.assertEqual(result["summary"]["total"], 0)
        self.assertEqual(result["summary"]["average_potential"], 0.0)

    def test_empty_dataset_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "没有可分析地块"):
            analyze_regeneration([])


if __name__ == "__main__":
    unittest.main()
