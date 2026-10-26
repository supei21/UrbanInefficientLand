from __future__ import annotations

import math
import unittest

from tianshu_core.tools.model_features import (
    build_model_feature_frame,
    make_feature_schema,
)


class ModelFeatureTest(unittest.TestCase):
    def test_schema_removes_duplicate_geometry_and_direct_coordinates(self):
        schema = make_feature_schema(["1", "7"])
        features = schema["feature_names"]
        self.assertNotIn("Shape_Area", features)
        self.assertNotIn("Shape_Leng", features)
        self.assertNotIn("centroid_x", features)
        self.assertNotIn("centroid_y", features)
        self.assertNotIn("Bulit_CHAG", features)
        self.assertFalse(any("project" in feature.lower() for feature in features))

    def test_dominant_landuse_is_one_hot_encoded(self):
        schema = make_feature_schema(["1", "7"])
        frame, _ = build_model_feature_frame(
            [{"dominant_l": "7", "centroid_x": 0, "centroid_y": 0}],
            schema["feature_names"],
            schema,
        )
        self.assertEqual(frame.loc[0, "dominant_l__7"], 1.0)
        self.assertEqual(frame.loc[0, "dominant_l__1"], 0.0)
        self.assertEqual(frame.loc[0, "dominant_l__OTHER"], 0.0)

    def test_canonical_upload_fields_map_back_to_training_features(self):
        schema = make_feature_schema(["7"])
        frame, _ = build_model_feature_frame(
            [
                {
                    "dominant_landuse": "7",
                    "poi_industry": 12,
                    "pop_density": 3456,
                    "night_light_mean": 8.5,
                    "previous_construction_ratio": 0.4,
                    "centroid_x": 100,
                    "centroid_y": 100,
                }
            ],
            schema["feature_names"],
            schema,
        )
        self.assertEqual(frame.loc[0, "poi_indust"], 12)
        self.assertEqual(frame.loc[0, "Pop_densit"], 3456)
        self.assertEqual(frame.loc[0, "NTL_MEAN"], 8.5)
        self.assertEqual(frame.loc[0, "Bulit_prop"], 0.4)

    def test_neighbourhood_density_uses_coordinates_without_exposing_them(self):
        schema = make_feature_schema(["7"])
        records = [
            {"dominant_l": "7", "centroid_x": 0, "centroid_y": 0, "poi_total": 10},
            {"dominant_l": "7", "centroid_x": 300, "centroid_y": 0, "poi_total": 20},
            {"dominant_l": "7", "centroid_x": 2000, "centroid_y": 0, "poi_total": 100},
        ]
        frame, _ = build_model_feature_frame(records, schema["feature_names"], schema)
        expected = 30 / (math.pi * 0.5**2)
        self.assertAlmostEqual(frame.loc[0, "poi_total__nbr_density_500m"], expected)
        self.assertNotIn("centroid_x", frame.columns)
        self.assertNotIn("centroid_y", frame.columns)


if __name__ == "__main__":
    unittest.main()
