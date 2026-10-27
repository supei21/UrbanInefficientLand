"""Corrected six-dimension low-efficiency evaluation for Wuhan blocks.

The formulas follow the 2026-10-25 corrected trial. Percentile ranks are
calculated only over blocks inside the urban development boundary when an
overlap ratio is available. Missing numeric indicators have percentile 50.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

DIMENSION_WEIGHTS = {
    "土地利用不足": 0.25,
    "城市活力不足": 0.25,
    "功能结构失配": 0.20,
    "公共服务短板": 0.15,
    "交通可达性不足": 0.10,
    "空间品质问题": 0.05,
}


def _first(block: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = block.get(name)
        if value is None or value == "" or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return None


def _rank(values: list[float | None]) -> pd.Series:
    """Match pandas average-tie percentile ranks used by the corrected trial."""

    return pd.Series(values, dtype="float64").rank(method="average", pct=True).fillna(0.5) * 100


def _level(score: float, dimensions: dict[str, float]) -> str:
    over_60 = sum(value >= 60 for value in dimensions.values())
    over_55 = sum(value >= 55 for value in dimensions.values())
    if score >= 65 and over_60 >= 3:
        return "高度低效"
    if score >= 60 and over_60 >= 2:
        return "明显低效"
    if score >= 55 and over_55 >= 2:
        return "疑似低效"
    return "一般"


def _entropy(block: dict[str, Any]) -> float | None:
    categories = [
        _first(block, "poi_indust", "poi_industry", "poi_industrial") or 0.0,
        _first(block, "poi_commer", "poi_commercial", "commercial_poi") or 0.0,
        _first(block, "poi_public", "poi_public_service", "public_service_poi") or 0.0,
        _first(block, "poi_transp", "poi_transport", "transport_poi") or 0.0,
        _first(block, "poi_logist", "poi_logistics") or 0.0,
    ]
    total = sum(categories)
    if total <= 0:
        return None
    shares = [value / total for value in categories if value > 0]
    return -sum(share * math.log(share) for share in shares) / math.log(5)


def evaluate_low_efficiency(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score eligible blocks using the corrected six-dimension trial formulas."""

    eligible: list[tuple[int, dict[str, Any]]] = []
    for index, block in enumerate(blocks):
        overlap = _first(block, "boundary_overlap_ratio", "udb_ratio")
        if overlap is not None and overlap < 0.5:
            continue
        if overlap is None and block.get("inside_boundary") is False:
            continue
        eligible.append((index, block))
    if not eligible:
        raise ValueError("当前数据集没有位于开发边界内的可分析地块")

    records: list[dict[str, float | None]] = []
    for _, block in eligible:
        area = _first(block, "geometry_area_km2", "area_km2")
        if area is None:
            shape_area = _first(block, "Shape_Area")
            area = shape_area / 1_000_000 if shape_area is not None else None
        current = _first(
            block,
            "Bulit_Area",
            "CURR_B2026",
            "built_current",
            "built_area_ratio",
            "construction_ratio",
        )
        previous = _first(block, "PREV_B2021", "Bulit_pro2")
        if previous is None:
            # The SHP importer maps 2021 Bulit_pro2 to construction_ratio.
            # Its previous_construction_ratio describes an earlier year.
            previous = (
                _first(block, "construction_ratio", "previous_construction_ratio")
                if _first(block, "Bulit_Area") is not None
                else _first(block, "previous_construction_ratio")
            )
        change = (
            current - previous
            if current is not None and previous is not None
            else _first(block, "CHG_21_26", "built_change", "construction_change")
        )
        public = _first(block, "poi_public", "poi_public_service", "public_service_poi")
        transport = _first(block, "poi_transp", "poi_transport", "transport_poi")
        logistics = _first(block, "poi_logist", "poi_logistics")
        industry = _first(block, "poi_indust", "poi_industry", "poi_industrial")
        commercial = _first(block, "poi_commer", "poi_commercial", "commercial_poi")
        poi_total = _first(block, "poi_total")
        if poi_total is None:
            poi_total = sum(
                value or 0.0 for value in (industry, commercial, public, transport, logistics)
            )
        shape_area = _first(block, "Shape_Area")
        shape_length = _first(block, "Shape_Leng")
        compactness = (
            max(0.0, min(1.0, 4 * math.pi * shape_area / shape_length**2))
            if shape_area is not None and shape_length is not None and shape_length > 0
            else _first(block, "compactness")
        )
        records.append(
            {
                "built": current,
                "built_change": change,
                "night_light": _first(block, "NTL_MEAN", "night_light_mean", "ntl_mean"),
                "poi_density": _first(block, "poi_densit", "poi_density", "poi_density_per_km2"),
                "population": _first(block, "Pop_densit", "pop_density", "pop_density_per_km2"),
                "public_density": public / max(area, 0.001)
                if public is not None and area is not None
                else None,
                "road_density": _first(
                    block, "road_densi", "road_density", "road_density_km_per_km2"
                ),
                "transport_density": (transport + (logistics or 0.0)) / max(area, 0.001)
                if transport is not None and area is not None
                else None,
                "compactness": compactness,
                "poi_total": poi_total,
                "industry_logistics_share": (industry or 0.0) / poi_total
                + (logistics or 0.0) / poi_total
                if poi_total > 0
                else 0.0,
                "functional_entropy": _entropy(block),
                "area": area,
            }
        )

    ranks = {
        name: _rank([record[name] for record in records])
        for name in (
            "built",
            "built_change",
            "night_light",
            "poi_density",
            "population",
            "public_density",
            "road_density",
            "transport_density",
            "compactness",
        )
    }
    results: list[dict[str, Any]] = []
    for index, (source_index, block) in enumerate(eligible):
        row = records[index]
        activity_rank = (
            ranks["night_light"][index] + ranks["poi_density"][index] + ranks["population"][index]
        ) / 3
        mismatch = max(ranks["built"][index] - activity_rank, 0.0)
        entropy = row["functional_entropy"]
        singularity = 65.0 if row["poi_total"] < 5 or entropy is None else (1 - entropy) * 100
        dimensions = {
            "土地利用不足": 0.40 * (100 - ranks["built"][index])
            + 0.25 * (100 - ranks["built_change"][index])
            + 0.35 * mismatch,
            "城市活力不足": 0.40 * (100 - ranks["night_light"][index])
            + 0.30 * (100 - ranks["poi_density"][index])
            + 0.30 * (100 - ranks["population"][index]),
            "功能结构失配": max(
                0.0, min(100.0, 0.70 * singularity + 0.30 * row["industry_logistics_share"] * 100)
            ),
            "公共服务短板": 100 - ranks["public_density"][index],
            "交通可达性不足": 0.60 * (100 - ranks["road_density"][index])
            + 0.40 * (100 - ranks["transport_density"][index]),
            "空间品质问题": 100 - ranks["compactness"][index],
        }
        score = float(
            np.round(
                sum(dimensions[name] * weight for name, weight in DIMENSION_WEIGHTS.items()), 2
            )
        )
        level = _level(score, dimensions)
        overlap = _first(block, "boundary_overlap_ratio", "udb_ratio")
        eco = _first(block, "ecological_overlap_ratio", "ecological_ratio", "eco_ratio") or 0.0
        farm = _first(block, "farmland_overlap_ratio", "farmland_ratio", "farm_ratio") or 0.0
        area = row["area"]
        constraint_review = eco > 0.01 or farm > 0.01
        geometry_review = area is not None and (area < 0.005 or area > 3.0)
        boundary_review = overlap is not None and 0.45 <= overlap <= 0.55
        issues = [
            label
            for flag, label in (
                (constraint_review, "约束"),
                (geometry_review, "几何"),
                (boundary_review, "边界"),
            )
            if flag
        ]
        status = (
            "非候选"
            if level == "一般"
            else ("候选-需" + "、".join(issues) + "复核" if issues else "候选-可进一步筛选")
        )
        coverage = round(
            sum(
                row[name] is not None
                for name in (
                    "built",
                    "built_change",
                    "night_light",
                    "poi_density",
                    "population",
                    "public_density",
                    "road_density",
                    "transport_density",
                    "compactness",
                )
            )
            / 9,
            2,
        )
        dominant = max(dimensions, key=dimensions.__getitem__)
        results.append(
            {
                "source_index": source_index,
                "inefficiency_score": score,
                "inefficiency_level": level,
                "inefficiency_dimensions": {
                    name: round(value, 2) for name, value in dimensions.items()
                },
                "dominant_problem": dominant,
                "screening_status": status,
                "data_coverage": coverage,
                "manual_review_required": level != "一般" and bool(issues),
                "key_evidence": [
                    f"{name} {dimensions[name]:.1f}"
                    for name in sorted(dimensions, key=dimensions.__getitem__, reverse=True)[:3]
                ],
            }
        )
    return results
