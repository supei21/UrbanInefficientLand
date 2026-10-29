from __future__ import annotations

from tianshu_core.low_efficiency import DIMENSION_WEIGHTS, evaluate_low_efficiency


def test_corrected_2026_built_field_and_boundary_filter() -> None:
    blocks = [
        {
            "block_id": "A",
            "boundary_overlap_ratio": 0.8,
            "Bulit_Area": 1.0,
            "Bulit_pro2": 0.0,
        },
        {
            "block_id": "B",
            "boundary_overlap_ratio": 0.8,
            "Bulit_Area": 0.0,
            "Bulit_pro2": 0.0,
        },
        {
            "block_id": "OUTSIDE",
            "boundary_overlap_ratio": 0.2,
            "Bulit_Area": 0.5,
        },
    ]

    results = evaluate_low_efficiency(blocks)

    assert [item["source_index"] for item in results] == [0, 1]
    assert len(DIMENSION_WEIGHTS) == 6
    assert results[0]["inefficiency_dimensions"]["土地利用不足"] == 17.5
    assert results[1]["inefficiency_dimensions"]["土地利用不足"] == 32.5
    assert all(item["inefficiency_level"] == "一般" for item in results)


def test_imported_shp_uses_construction_ratio_as_2021_value() -> None:
    imported = [
        {
            "block_id": "A",
            "Bulit_Area": 0.8,
            "construction_ratio": 0.2,
            "previous_construction_ratio": 0.9,
        },
        {
            "block_id": "B",
            "Bulit_Area": 0.4,
            "construction_ratio": 0.4,
            "previous_construction_ratio": 0.1,
        },
    ]
    direct = [
        {"block_id": "A", "Bulit_Area": 0.8, "Bulit_pro2": 0.2},
        {"block_id": "B", "Bulit_Area": 0.4, "Bulit_pro2": 0.4},
    ]

    assert evaluate_low_efficiency(imported) == evaluate_low_efficiency(direct)
