from __future__ import annotations

import unittest

from tianshu_core.regeneration_geojson import build_regeneration_point_geojson


class RegenerationGeoJsonTests(unittest.TestCase):
    def test_projected_centroid_is_transformed_for_web_map(self) -> None:
        layer = build_regeneration_point_geojson(
            [
                {
                    "block_id": "WH-1",
                    "block_name": "测试单元",
                    "district": "江岸区",
                    "lng": 521629.293,
                    "lat": 3329814.001,
                }
            ],
            [
                {
                    "block_id": "WH-1",
                    "regeneration_scenario": "重点再生",
                    "priority_score": 98.0,
                    "inefficiency_score": 72.0,
                    "regeneration_potential": 80.0,
                    "scenario_actions": ["公共空间织补"],
                }
            ],
        )

        feature = layer["features"][0]
        longitude, latitude = feature["geometry"]["coordinates"]
        self.assertAlmostEqual(longitude, 114.2244, places=3)
        self.assertAlmostEqual(latitude, 30.0873, places=3)
        self.assertEqual(feature["properties"]["regeneration_scenario"], "重点再生")


if __name__ == "__main__":
    unittest.main()
