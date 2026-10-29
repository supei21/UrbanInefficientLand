"""Low-efficiency space identification and regeneration scenario planning.

The competition workflow is intentionally deterministic: it accepts heterogeneous
block attributes, derives comparable 0-100 scores, records data coverage, and
returns an explainable two-dimensional classification for every block.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Iterable
from typing import Any

from tianshu_core.low_efficiency import DIMENSION_WEIGHTS, evaluate_low_efficiency

CANDIDATE_LEVELS = ("高度低效", "明显低效")
DEVELOPMENT_DIRECTIONS = {
    "第二产业": ("sec_prob", "盘活低效产业载体", "导入先进制造与研发创新"),
    "第三产业": ("ter_prob", "补充商业和社区服务", "完善教育医疗等公共服务"),
    "交通": ("tra_prob", "改善站点衔接与慢行系统", "优化物流组织和节点空间"),
}
POTENTIAL_LEVELS = ("低", "较低", "中", "较高", "高")
COMPOSITE_DIRECTION_GAP = 0.05


SCENARIOS = {
    "优先更新": {
        "positioning": "高度低效、潜力较高的优先更新区",
        "actions": ["盘活存量空间", "导入适宜功能", "完善公共服务", "改善交通衔接"],
        "timing": "近期启动（1—2年）",
        "color": "#e85d3f",
    },
    "提质改善": {
        "positioning": "明显低效、潜力较高的渐进改善区",
        "actions": ["补充公共服务", "提升空间品质", "优化现有功能", "分期完善基础设施"],
        "timing": "分期推进（2—5年）",
        "color": "#f2a541",
    },
    "生态修复或储备": {
        "positioning": "刚性约束修复或低潜力弹性储备区",
        "actions": ["核验规划约束", "整治突出问题", "控制开发强度", "定期复评"],
        "timing": "分类治理与动态复评",
        "color": "#657153",
    },
    "持续观察": {
        "positioning": "明显低效、潜力较低的持续观察区",
        "actions": ["维持必要维护", "补齐基础设施短板", "监测活力变化", "定期复评更新机会"],
        "timing": "持续监测",
        "color": "#4f9d69",
    },
}

SCENARIO_SUBTYPES = {
    "生态修复": {
        "positioning": "受刚性约束影响的保护修复区",
        "actions": ["生态保育", "污染与风险治理", "建设活动退出", "蓝绿网络修复"],
        "timing": "约束优先、分类治理",
    },
    "储备": {
        "positioning": "高度低效、潜力较低的弹性储备区",
        "actions": ["安全隐患整治", "控制开发强度", "保留远期更新弹性", "定期复评潜力"],
        "timing": "中长期储备与动态复评",
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


def _development_ranks(blocks: list[dict[str, Any]]) -> dict[str, list[float]]:
    """Rank each XGBoost probability against every uploaded city block."""

    ranks: dict[str, list[float]] = {}
    for direction, (field, _, _) in DEVELOPMENT_DIRECTIONS.items():
        values = [_number(block, (field,)) for block in blocks]
        if any(value is None or not 0 <= value <= 1 for value in values):
            raise ValueError(f"街区数据缺少完整有效的 {field}（{direction} XGBoost 概率）")
        ordered = sorted(value for value in values if value is not None)
        size = len(ordered)
        ranks[direction] = [
            (bisect_left(ordered, value) + bisect_right(ordered, value) - 1) / (2 * (size - 1))
            if size > 1
            else 0.5
            for value in values
            if value is not None
        ]
    return ranks


def _potential_level(score: float) -> str:
    return POTENTIAL_LEVELS[min(int(score / 20), 4)]


def _development_actions(directions: list[str]) -> list[str]:
    return [action for direction in directions for action in DEVELOPMENT_DIRECTIONS[direction][1:]]


def _hard_constraint_reasons(block: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if (
        block.get("ecological_redline") is True
        or (_number(block, ("ecological_overlap_ratio", "ecological_ratio", "eco_ratio")) or 0.0)
        > 0.01
    ):
        reasons.append("生态保护红线")
    if (
        block.get("permanent_farmland") is True
        or (_number(block, ("farmland_overlap_ratio", "farmland_ratio", "farm_ratio")) or 0.0)
        > 0.01
    ):
        reasons.append("永久基本农田")
    if block.get("prohibited_disaster_zone") is True:
        reasons.append("地质灾害禁止建设区")
    return reasons


def _scenario(
    inefficiency_level: str,
    potential: float,
    constraint_reasons: list[str],
    potential_threshold: float,
) -> tuple[str, str | None, str]:
    if inefficiency_level not in CANDIDATE_LEVELS:
        raise ValueError("再生场景仅对高度低效和明显低效地块计算")
    if constraint_reasons:
        return (
            "生态修复或储备",
            "生态修复",
            f"涉及{'、'.join(constraint_reasons)}，应优先开展约束核验与保护修复",
        )
    high_potential = potential >= potential_threshold
    if inefficiency_level == "高度低效":
        if high_potential:
            return "优先更新", None, "高度低效且再生潜力达到阈值"
        return "生态修复或储备", "储备", "高度低效但再生潜力低于阈值，保留远期更新弹性"
    if high_potential:
        return "提质改善", None, "明显低效且再生潜力达到阈值"
    return "持续观察", None, "明显低效且再生潜力低于阈值，持续监测更新机会"


def analyze_regeneration(
    blocks: list[dict[str, Any]],
    *,
    potential_threshold: float = 50.0,
) -> dict[str, Any]:
    """Analyze blocks and return explainable regeneration decisions and summary."""

    if not blocks:
        raise ValueError("当前数据集没有可分析地块")

    low_efficiency = [
        result
        for result in evaluate_low_efficiency(blocks)
        if result["inefficiency_level"] in CANDIDATE_LEVELS
    ]
    candidate_blocks = [blocks[result["source_index"]] for result in low_efficiency]
    development_ranks = _development_ranks(blocks) if candidate_blocks else {}

    decisions: list[dict[str, Any]] = []
    for index, low_result in enumerate(low_efficiency):
        block = candidate_blocks[index]
        source_index = low_result["source_index"]
        inefficiency = low_result["inefficiency_score"]
        direction_ranks = {
            direction: values[source_index] for direction, values in development_ranks.items()
        }
        best_rank = max(direction_ranks.values())
        leading_directions = [
            direction
            for direction, value in direction_ranks.items()
            if best_rank - value <= COMPOSITE_DIRECTION_GAP
        ]
        development_type = (
            leading_directions[0]
            if len(leading_directions) == 1
            else "、".join(leading_directions) + "（复合）"
        )
        potential = round(best_rank * 100, 2)
        potential_level = _potential_level(potential)
        direction_actions = _development_actions(leading_directions)
        direction_probabilities = {
            direction: _number(block, (field,))
            for direction, (field, _, _) in DEVELOPMENT_DIRECTIONS.items()
        }
        constraint_reasons = _hard_constraint_reasons(block)
        hard_constraint = bool(constraint_reasons)
        scenario_name, scenario_subtype, scenario_reason = _scenario(
            low_result["inefficiency_level"],
            potential,
            constraint_reasons,
            potential_threshold,
        )
        scenario = SCENARIOS[scenario_name]
        subtype_details = SCENARIO_SUBTYPES.get(scenario_subtype or "", {})
        scenario_actions = list(subtype_details.get("actions", scenario["actions"]))
        if not hard_constraint and potential >= potential_threshold:
            scenario_actions.extend(direction_actions)
        priority_raw = round(
            inefficiency * 0.45
            + potential * 0.35
            + min(inefficiency, potential) * 0.20
            + {"优先更新": 15, "提质改善": 4, "生态修复或储备": 3}.get(scenario_name, 0),
            2,
        )
        decisions.append(
            {
                "block_id": str(
                    block.get("block_id")
                    or block.get("object_id")
                    or low_result["source_index"] + 1
                ),
                "block_name": block.get("block_name") or block.get("district") or "未命名地块",
                "district": block.get("district"),
                "inefficiency_score": inefficiency,
                "regeneration_potential": potential,
                "dev_score": round(best_rank, 6),
                "dev_type": development_type,
                "development_directions": leading_directions,
                "development_probabilities": direction_probabilities,
                "development_ranks": {
                    key: round(value, 6) for key, value in direction_ranks.items()
                },
                "potential_level": potential_level,
                "priority_score": 0.0,
                "priority_index_raw": priority_raw,
                "priority_level": "待排序",
                "regeneration_scenario": scenario_name,
                "scenario_subtype": scenario_subtype,
                "scenario_reason": scenario_reason,
                "constraint_reasons": constraint_reasons,
                "scenario_positioning": subtype_details.get("positioning", scenario["positioning"]),
                "scenario_actions": scenario_actions,
                "implementation_timing": subtype_details.get("timing", scenario["timing"]),
                "scenario_color": scenario["color"],
                "inefficiency_dimensions": low_result["inefficiency_dimensions"],
                "inefficiency_level": low_result["inefficiency_level"],
                "dominant_problem": low_result["dominant_problem"],
                "screening_status": low_result["screening_status"],
                "potential_dimensions": {
                    key: round(value * 100, 2) for key, value in direction_ranks.items()
                },
                "data_coverage": low_result["data_coverage"],
                "manual_review_required": low_result["manual_review_required"] or hard_constraint,
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
            "candidate_levels": list(CANDIDATE_LEVELS),
            "inefficiency_levels": {
                "高度低效": "得分≥65且至少3维≥60",
                "明显低效": "得分≥60且至少2维≥60",
            },
            "potential_method": "三方向 XGBoost 概率分别换算为全市相对位次，取最高位次为 DEV_SCORE",
            "potential_reference_count": len(blocks),
            "potential_levels": list(POTENTIAL_LEVELS),
            "composite_direction_gap": COMPOSITE_DIRECTION_GAP,
            "classification": "高度/明显低效等级 × DEV_SCORE 高低；刚性约束优先校核",
        },
        "summary": {
            "total": len(decisions),
            "candidate_count": len(decisions),
            "inefficiency_level_counts": {
                level: sum(item["inefficiency_level"] == level for item in decisions)
                for level in CANDIDATE_LEVELS
            },
            "priority_count": priority_counts.get("近期重点", 0),
            "manual_review_count": sum(item["manual_review_required"] for item in decisions),
            "average_inefficiency": round(
                sum(item["inefficiency_score"] for item in decisions) / len(decisions), 2
            )
            if decisions
            else 0.0,
            "average_potential": round(
                sum(item["regeneration_potential"] for item in decisions) / len(decisions), 2
            )
            if decisions
            else 0.0,
            "scenario_counts": {name: scenario_counts.get(name, 0) for name in SCENARIOS},
            "priority_counts": dict(priority_counts),
        },
        "decisions": decisions,
        "scenario_catalog": SCENARIOS,
        "disclaimer": "结果用于竞赛研究与更新项目初筛，不替代法定规划、权属核验和工程可行性论证。",
    }
