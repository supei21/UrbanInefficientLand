from __future__ import annotations

import json
import unittest
from pathlib import Path

from tianshu_core.config import load_config
from tianshu_core.io import parse_json
from tianshu_core.paths import SAMPLE_DATA_FILE
from tianshu_core.spatial.shapefile import read_shapefile_zip_path
from tianshu_core.tools.trained_model import (
    ENGINEERED_FEATURE_SOURCES,
    TrainedBoundaryModelError,
    enrich_blocks_with_model_predictions,
    model_status,
    resolve_model_dir,
)
from tianshu_core.workflow.graph import run_workflow


class TrainedModelToolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.model_dir = resolve_model_dir(cls.config)
        cls.blocks = parse_json(SAMPLE_DATA_FILE.read_bytes())

    def test_model_status_reports_configured_model(self):
        status = model_status(self.config)
        self.assertTrue(status["enabled"])
        self.assertEqual(Path(status["model_dir"]), self.model_dir)
        if (self.model_dir / "feature_names.json").exists():
            self.assertGreater(status["feature_count"], 0)

    def test_uploaded_development_potential_is_used_before_xgboost(self):
        config = {"trained_model": {"enabled": False}}
        blocks = [
            {"block_id": "P001", "inside_boundary": False, "development_potential": 0.93},
            {"block_id": "P002", "inside_boundary": False, "development_potential": 0.81},
        ]
        bundle = enrich_blocks_with_model_predictions(blocks, config)
        self.assertEqual(bundle.source, "uploaded_development_potential")
        self.assertEqual(bundle.model_dir, "input:dev_score")
        self.assertEqual(bundle.blocks[0]["development_probability"], 93.0)
        self.assertEqual(bundle.blocks[1]["development_probability"], 81.0)

    def test_partial_development_potential_is_rejected(self):
        blocks = [
            {"block_id": "P001", "inside_boundary": False, "development_potential": 0.93},
            {"block_id": "P002", "inside_boundary": False},
        ]
        with self.assertRaisesRegex(TrainedBoundaryModelError, "字段不完整"):
            enrich_blocks_with_model_predictions(blocks, self.config)

    def test_actual_adjustment_model_outputs_three_probabilities_and_shap(self):
        model_path = self.model_dir / "xgb_boundary.json"
        manifest_path = self.model_dir / "model_manifest.json"
        feature_path = self.model_dir / "feature_names.json"
        if not (model_path.exists() or manifest_path.exists()) or not feature_path.exists():
            self.skipTest("actual-adjustment model is not installed")
        feature_names = json.loads(feature_path.read_text(encoding="utf-8"))
        block = {feature: 0.0 for feature in feature_names}
        for sources in ENGINEERED_FEATURE_SOURCES.values():
            block.update({feature: 0.0 for feature in sources})
        block.update({"block_id": "UNIT_TEST_BLOCK", "inside_boundary": False})
        bundle = enrich_blocks_with_model_predictions([block], self.config)
        if bundle.class_count != 3:
            self.skipTest("configured model is not an adjustment model")
        predicted = bundle.blocks[0]
        self.assertIn(bundle.model_type, {"multiclass_adjustment", "dual_binary_adjustment"})
        self.assertIn(bundle.source, {"actual_adjustment_xgb_json", "optimized_dual_xgb_json"})
        for name in ["prob_no_change", "prob_inclusion", "prob_exclusion"]:
            self.assertGreaterEqual(predicted[name], 0.0)
            self.assertLessEqual(predicted[name], 1.0)
        if bundle.model_type == "multiclass_adjustment":
            self.assertAlmostEqual(
                predicted["prob_no_change"]
                + predicted["prob_inclusion"]
                + predicted["prob_exclusion"],
                1.0,
                places=5,
            )
        self.assertIn(predicted["adjustment_label"], bundle.class_names)
        self.assertTrue(predicted["shap_inclusion_drivers"])
        self.assertTrue(predicted["shap_exclusion_drivers"])

    @unittest.skipUnless(
        Path(r"E:\VscodeMyPrograma\tianshu_core_demo\models\xgb_boundary.json").exists(),
        "trained model JSON is not available on this machine",
    )
    def test_sparse_demo_blocks_fall_back_instead_of_forcing_model(self):
        with self.assertRaises(TrainedBoundaryModelError):
            enrich_blocks_with_model_predictions(self.blocks, self.config)

    @unittest.skipUnless(
        Path(r"E:\VscodeMyPrograma\tianshu_core_demo\models\xgb_boundary.json").exists(),
        "trained model JSON is not available on this machine",
    )
    def test_workflow_falls_back_for_sparse_demo_blocks(self):
        result = run_workflow(self.blocks, self.config, include_ai_explanations=False)
        trained_model = result["summary"]["trained_model"]
        self.assertFalse(trained_model["applied"])
        self.assertIn("回退", trained_model["warning"])
        self.assertEqual(result["summary"]["total"], len(self.blocks))

    @unittest.skipUnless(
        Path(r"E:\VscodeMyPrograma\tianshu_core_demo\models\xgb_boundary.json").exists()
        and Path(
            r"D:\downloadzhuomian\城镇开发边界\初步筛选调整地块\初步筛选调整地块.zip"
        ).exists(),
        "trained model or candidate parcel ZIP is not available on this machine",
    )
    def test_enrich_blocks_adds_development_probability(self):
        dataset = read_shapefile_zip_path(
            "初步筛选调整地块",
            Path(r"D:\downloadzhuomian\城镇开发边界\初步筛选调整地块\初步筛选调整地块.zip"),
        )
        self.addCleanup(dataset.close)
        bundle = enrich_blocks_with_model_predictions(dataset.blocks[:10], self.config)
        self.assertEqual(len(bundle.blocks), 10)
        self.assertGreater(bundle.feature_count, 0)
        for block in bundle.blocks:
            self.assertIn("development_probability", block)
            self.assertGreaterEqual(block["development_probability"], 0)
            self.assertLessEqual(block["development_probability"], 100)

    @unittest.skipUnless(
        Path(r"E:\VscodeMyPrograma\tianshu_core_demo\models\xgb_boundary.json").exists()
        and Path(
            r"D:\downloadzhuomian\城镇开发边界\初步筛选调整地块\初步筛选调整地块.zip"
        ).exists(),
        "trained model or candidate parcel ZIP is not available on this machine",
    )
    def test_workflow_uses_model_probability_when_enriched(self):
        dataset = read_shapefile_zip_path(
            "初步筛选调整地块",
            Path(r"D:\downloadzhuomian\城镇开发边界\初步筛选调整地块\初步筛选调整地块.zip"),
        )
        self.addCleanup(dataset.close)
        bundle = enrich_blocks_with_model_predictions(dataset.blocks[:10], self.config)
        result = run_workflow(dataset.blocks[:10], self.config, include_ai_explanations=False)
        model_scores = {
            str(block["block_id"]): round(float(block["development_probability"]), 2)
            for block in bundle.blocks
        }
        self.assertTrue(result["summary"]["trained_model"]["applied"])
        for decision in result["decisions"]:
            self.assertEqual(
                round(float(decision["development_probability"]), 2),
                model_scores[str(decision["block_id"])],
            )


if __name__ == "__main__":
    unittest.main()
