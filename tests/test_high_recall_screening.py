import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from tianshu_core.tools import trained_model as tm


class ConstantPredictor:
    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, frame):
        return np.full(len(frame), self.probability)


class HighRecallScreeningTests(unittest.TestCase):
    def test_prefer_adjustment_model_prevents_old_dev_score_bypass(self):
        with tempfile.TemporaryDirectory() as temp:
            model_dir = Path(temp)
            (model_dir / "model_manifest.json").write_text(
                json.dumps({"model_type": "dual_binary_adjustment"})
            )
            config = {
                "trained_model": {
                    "enabled": True,
                    "model_dir": str(model_dir),
                    "prefer_adjustment_model": True,
                }
            }
            with patch.object(
                tm, "_dual_binary_prediction_bundle", return_value="actual-model-called"
            ) as invoke:
                result = tm.enrich_blocks_with_model_predictions(
                    [{"block_id": "A", "dev_score": 0.9}], config
                )
            self.assertEqual(result, "actual-model-called")
            invoke.assert_called_once()

    def test_legacy_profile_still_accepts_development_potential(self):
        result = tm.enrich_blocks_with_model_predictions(
            [{"block_id": "A", "dev_score": 0.9}], {"trained_model": {"enabled": False}}
        )
        self.assertEqual(result.source, "uploaded_development_potential")

    def test_both_directions_survive_independent_screening(self):
        manifest = {"thresholds": {"inclusion": 0.5, "exclusion": 0.5}}
        predictors = (
            ConstantPredictor(0.8),
            ["road_lengt"],
            ConstantPredictor(0.9),
            ["road_lengt"],
            manifest,
        )
        with (
            patch.object(tm, "load_dual_predictors", return_value=predictors),
            patch.object(tm, "load_shap_explanations", return_value=({}, {}, [], [])),
        ):
            result = tm._dual_binary_prediction_bundle(
                [
                    {"block_id": "A", "road_lengt": 1, "inside_boundary": True},
                    {"block_id": "B", "road_lengt": 1, "inside_boundary": False},
                ],
                Path("."),
                {},
            )
        for row in result.blocks:
            self.assertTrue(row["screening_inclusion"])
            self.assertTrue(row["screening_exclusion"])
            self.assertEqual(row["screening_stage"], "model_only_requires_spatial_policy_review")
        # Final direction-aware model class is still distinct from review signals.
        self.assertEqual(result.blocks[0]["adjustment_class"], 2)
        self.assertEqual(result.blocks[1]["adjustment_class"], 1)


if __name__ == "__main__":
    unittest.main()
