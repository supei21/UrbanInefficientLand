from __future__ import annotations

import unittest

import pandas as pd

from scripts.train_xgboost import build_change_labels


class ChangeLabelTest(unittest.TestCase):
    def test_requires_ratio_and_absolute_area(self):
        source = pd.DataFrame(
            {
                "Bulit_CHAG": [0.02, 0.02, 0.008, 0.02],
                "area_km2": [0.10, 0.01, 1.00, 0.05],
            }
        )
        valid, labels, change_area = build_change_labels(source, 0.01, 1000)
        self.assertEqual(valid.tolist(), [True] * 4)
        self.assertEqual(labels.tolist(), [1, 0, 0, 0])
        self.assertAlmostEqual(change_area.iloc[0], 2000)
        self.assertAlmostEqual(change_area.iloc[3], 1000)

    def test_excludes_invalid_area_and_ratio(self):
        source = pd.DataFrame(
            {
                "Bulit_CHAG": [0.2, None, 0.2],
                "area_km2": [0, 0.1, None],
            }
        )
        valid, _, _ = build_change_labels(source, 0.01, 1000)
        self.assertEqual(valid.tolist(), [False, False, False])

    def test_rejects_negative_threshold(self):
        source = pd.DataFrame({"Bulit_CHAG": [0.1], "area_km2": [0.1]})
        with self.assertRaises(ValueError):
            build_change_labels(source, 0.01, -1)


if __name__ == "__main__":
    unittest.main()
