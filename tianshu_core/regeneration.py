"""Low-efficiency space identification and regeneration scenario planning.

The competition workflow is intentionally deterministic: it accepts heterogeneous
block attributes, derives comparable 0-100 scores, records data coverage, and
returns an explainable two-dimensional classification for every block.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from tianshu_core.low_efficiency import DIMENSION_WEIGHTS, evaluate_low_efficiency

POTENTIAL_WEIGHTS = {
    "location_value": 0.30,
    "market_support": 0.25,
    "space_capacity": 0.25,
    "implementation_feasibility": 0.20,
}


FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "poi_density": ("poi_density", "poi_density_per_km2", "poi_densit"),
    "commercial": ("poi_commercial", "commercial_poi", "commercial_density", "poi_commer"),
    "public_service": ("poi_public", "poi_public_service", "public_service_poi"),
    "transport": ("poi_transport", "transport_poi", "transit_stop_count", "poi_transp"),
    "industry": ("poi_industry", "poi_industrial", "industrial_poi", "poi_indust"),
    "population_density": (
        "pop_density",
        "pop_density_per_km2",
        "population_density",
        "Pop_densit",
    ),
    "road_density": ("road_density", "road_density_km_per_km2", "road_densi"),
    "built_ratio": ("Bulit_Area", "built_area_ratio", "construction_ratio"),
    "vacancy": ("vacancy_rate", "vacant_ratio", "idle_land_ratio"),
    "building_age": ("building_age", "average_building_age"),
    "green_ratio": ("green_ratio", "tree_cover_ratio", "forest_ratio"),
    "mixed_use": ("mixed_use_index", "land_use_mix", "functional_mix"),
}


SCENARIOS = {
    "重点再生": {
        "positioning": "高低效、高潜力的优先启动区",
        "actions": ["复合功能导入", "公共空间织补", "存量建筑适应性再利用", "慢行与公共交通接驳"],
        "timing": "近期启动（1—2年）",
        "color": "#e85d3f",
    },
    "渐进更新": {
        "positioning": "问题突出但实施条件有限的持续治理区",
        "actions": ["安全隐患整治", "小微公共空间更新", "基础设施补短板", "低成本分期改造"],
        "timing": "分期推进（2—5年）",
        "color": "#f2a541",
    },
    "活力培育": {
        "positioning": "现状基础尚可、具备活力提升机会的培育区",
        "actions": ["社区服务嵌入", "首层界面激活", "特色业态导入", "公共活动运营"],
        "timing": "滚动实施（1—3年）",
        "color": "#2e86ab",
    },
    "稳定提升": {
        "positioning": "低低效、低潜力的品质维护与监测区",
        "actions": ["常态化维护", "15分钟生活圈补缺", "低扰动环境改善", "年度活力监测"],
        "timing": "持续维护",
        "color": "#4f9d69",
    },
    "生态修复": {
        "positioning": "受刚性约束影响的保护修复区",
        "actions": ["生态保育", "污染与风险治理", "建设活动退出", "蓝绿网络修复"],
        "timing": "约束优先、分类治理",
        "color": "#657153",
    },
}


def _number(block: dict[str, Any], names: Iterable[str]) -> float | None:
    for name in names:
        value = block.get(name)
        if value in (None, "") or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _series(blocks: list[dict[str, Any]], field_group: str) -> list[float | None]:
    names = FIELD_GROUPS[field_group]
    return [_number(block, names) for block in blocks]


def _normalize(values: list[float | None], *, inverse: bool = False) -> list[float | None]:
    present = sorted(value for value in values if value is not None)
    if not present:
        return [None] * len(values)
    low_index = max(0, int((len(present) - 1) * 0.05))
    high_index = min(len(present) - 1, int((len(present) - 1) * 0.95))
    low, high = present[low_index], present[high_index]
    span = high - low
    output: list[float | None] = []
    for value in values:
        if value is None:
            output.append(None)
            continue
        score = 50.0 if span <= 1e-12 else (value - low) / span * 100
        score = max(0.0, min(100.0, score))
        output.append(round(100 - score if inverse else score, 2))
    return output


def _mean_available(values: Iterable[float | None], default: float = 50.0) -> tuple[float, int]:
    present = [float(value) for value in values if value is not None]
    if not present:
        return default, 0
    return sum(present) / len(present), len(present)


def _weighted(dimensions: dict[str, float], weights: dict[str, float]) -> float:
    return round(sum(dimensions[key] * weight for key, weight in weights.items()), 2)


def _has_hard_constraint(block: dict[str, Any]) -> bool:
    return any(
        block.get(field) is True
        for field in ("ecological_redline", "permanent_farmland", "prohibited_disaster_zone")
    ) or any(
        (_number(block, names) or 0.0) > 0.01
        for names in (
            ("ecological_overlap_ratio", "ecological_ratio", "eco_ratio"),
            ("farmland_overlap_ratio", "farmland_ratio", "farm_ratio"),
        )
    )


def _scenario(
    inefficiency_level: str,
    potential: float,
    block: dict[str, Any],
    potential_threshold: float,
) -> str:
    if _has_hard_constraint(block):
        return "生态修复"
    clearly_inefficient = inefficiency_level in {"高度低效", "明显低效"}
    if clearly_inefficient and potential >= potential_threshold:
        return "重点再生"
    if clearly_inefficient:
        return "渐进更新"
    if potential >= potential_threshold:
        return "活力培育"
    return "稳定提升"


def analyze_regeneration(
    blocks: list[dict[str, Any]],
    *,
    potential_threshold: float = 50.0,
) -> dict[str, Any]:
    """Analyze blocks and return explainable regeneration decisions and summary."""

    if not blocks:
        raise ValueError("当前数据集没有可分析地块")

    low_efficiency = evaluate_low_efficiency(blocks)
    normalized = {
        "commercial": _normalize(_series(blocks, "commercial")),
        "transport": _normalize(_series(blocks, "transport")),
        "industry": _normalize(_series(blocks, "industry")),
        "population": _normalize(_series(blocks, "population_density")),
        "road": _normalize(_series(blocks, "road_density")),
        "built": _normalize(_series(blocks, "built_ratio")),
        "vacancy": _normalize(_series(blocks, "vacancy")),
        "green": _normalize(_series(blocks, "green_ratio")),
    }

    decisions: list[dict[str, Any]] = []
    for low_result in low_efficiency:
        index = low_result["source_index"]
        block = blocks[index]
        accessibility_positive, _ = _mean_available(
            [normalized["transport"][index], normalized["road"][index]]
        )
        inefficiency = low_result["inefficiency_score"]

        location_value = accessibility_positive
        market_support, _ = _mean_available(
            [
                normalized["commercial"][index],
                normalized["population"][index],
                normalized["industry"][index],
            ]
        )
        space_capacity, _ = _mean_available(
            [
                normalized["built"][index],
                normalized["green"][index],
                None
                if normalized["vacancy"][index] is None
                else 100 - normalized["vacancy"][index],
            ]
        )
        hard_constraint = _has_hard_constraint(block)
        disaster_risk = str(block.get("disaster_risk") or "").lower()
        feasibility = (
            15.0
            if hard_constraint
            else 45.0
            if disaster_risk in {"高", "high", "禁止建设", "prohibited"}
            else 85.0
        )
        potential_dimensions = {
            "location_value": round(location_value, 2),
            "market_support": round(market_support, 2),
            "space_capacity": round(space_capacity, 2),
            "implementation_feasibility": feasibility,
        }
        potential = _weighted(potential_dimensions, POTENTIAL_WEIGHTS)
        scenario_name = _scenario(
            low_result["inefficiency_level"],
            potential,
            block,
            potential_threshold,
        )
        scenario = SCENARIOS[scenario_name]
        priority_raw = round(
            inefficiency * 0.45
            + potential * 0.35
            + min(inefficiency, potential) * 0.20
            + {"重点再生": 15, "渐进更新": 4, "活力培育": 2, "生态修复": 3}.get(scenario_name, 0),
            2,
        )
        decisions.append(
            {
                "block_id": str(block.get("block_id") or block.get("object_id") or index + 1),
                "block_name": block.get("block_name") or block.get("district") or "未命名地块",
                "district": block.get("district"),
                "inefficiency_score": inefficiency,
                "regeneration_potential": potential,
                "priority_score": 0.0,
                "priority_index_raw": priority_raw,
                "priority_level": "待排序",
                "regeneration_scenario": scenario_name,
                "scenario_positioning": scenario["positioning"],
                "scenario_actions": scenario["actions"],
                "implementation_timing": scenario["timing"],
                "scenario_color": scenario["color"],
                "inefficiency_dimensions": low_result["inefficiency_dimensions"],
                "inefficiency_level": low_result["inefficiency_level"],
                "dominant_problem": low_result["dominant_problem"],
                "screening_status": low_result["screening_status"],
                "potential_dimensions": potential_dimensions,
                "data_coverage": low_result["data_coverage"],
                "manual_review_required": low_result["manual_review_required"],
                "key_evidence": low_result["key_evidence"],
            }
        )

    decisions.sort(key=lambda item: (-item["priority_index_raw"], item["block_id"]))
    total = len(decisions)
    for rank, item in enumerate(decisions, start=1):
        item["rank"] = rank
        percentile = round((total - rank + 1) / total * 100, 2)
        item["priority_score"] = percentile
        item["priority_level"] = (
            "近期重点" if percentile >= 90 else "中期储备" if percentile >= 60 else "持续监测"
        )

    scenario_counts = Counter(item["regeneration_scenario"] for item in decisions)
    priority_counts = Counter(item["priority_level"] for item in decisions)
    return {
        "type": "regeneration_analysis",
        "title": "低效空间识别与再生场景策划",
        "method": {
            "potential_threshold": potential_threshold,
            "inefficiency_weights": DIMENSION_WEIGHTS,
            "inefficiency_method": "修正后的六维百分位秩评价（2026年建设用地占比）",
            "inefficiency_levels": {
                "高度低效": "得分≥65且至少3维≥60",
                "明显低效": "得分≥60且至少2维≥60",
                "疑似低效": "得分≥55且至少2维≥55",
                "一般": "其余地块",
            },
            "potential_weights": POTENTIAL_WEIGHTS,
            "classification": "六维低效等级与再生潜力；得分用于散点图展示",
        },
        "summary": {
            "total": len(decisions),
            "candidate_count": sum(item["inefficiency_level"] != "一般" for item in decisions),
            "inefficiency_level_counts": dict(
                Counter(item["inefficiency_level"] for item in decisions)
            ),
            "priority_count": priority_counts.get("近期重点", 0),
            "manual_review_count": sum(item["manual_review_required"] for item in decisions),
            "average_inefficiency": round(
                sum(item["inefficiency_score"] for item in decisions) / len(decisions), 2
            ),
            "average_potential": round(
                sum(item["regeneration_potential"] for item in decisions) / len(decisions), 2
            ),
            "scenario_counts": dict(scenario_counts),
            "priority_counts": dict(priority_counts),
        },
        "decisions": decisions,
        "scenario_catalog": SCENARIOS,
        "disclaimer": "结果用于竞赛研究与更新项目初筛，不替代法定规划、权属核验和工程可行性论证。",
    }
