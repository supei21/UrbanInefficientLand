from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Polygon

from scripts.evaluate_low_efficiency_shp import FIELD_NOTES, _export_layer
from tianshu_core.low_efficiency import evaluate_low_efficiency


def test_shapefile_export_keeps_source_fields_and_evidence(tmp_path) -> None:
    blocks = [
        {
            "block_id": "A",
            "area_km2": 0.01,
            "boundary_overlap_ratio": 0.9,
            "ecological_ratio": 0.0,
            "farmland_ratio": 0.0,
            "Bulit_Area": 0.8,
            "construction_ratio": 0.2,
        },
        {
            "block_id": "B",
            "area_km2": 0.01,
            "boundary_overlap_ratio": 0.9,
            "ecological_ratio": 0.0,
            "farmland_ratio": 0.0,
            "Bulit_Area": 0.4,
            "construction_ratio": 0.4,
        },
    ]
    raw = gpd.GeoDataFrame(
        {
            "block_id": ["A", "B"],
            "name": ["甲", "乙"],
            "SRC_ECO": [0.0, 0.0],
            "geometry": [
                Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]),
                Polygon([(200, 0), (300, 0), (300, 100), (200, 100)]),
            ],
        },
        crs="EPSG:32650",
    )
    results = evaluate_low_efficiency(blocks)
    path = tmp_path / "evaluated.shp"

    _export_layer(raw, blocks, results, {}, path)

    exported = gpd.read_file(path, engine="pyogrio")
    assert len(exported) == 2
    assert exported.crs == raw.crs
    assert set(FIELD_NOTES).issubset(exported.columns)
    assert exported["name"].tolist() == ["甲", "乙"]
    assert exported["LE_SCORE"].tolist() == [item["inefficiency_score"] for item in results]
    assert exported["EVIDENCE"].str.count("；").eq(2).all()
    assert all(
        result["dominant_problem"] in evidence
        for result, evidence in zip(results, exported["EVIDENCE"], strict=True)
    )
