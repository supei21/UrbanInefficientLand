from __future__ import annotations

from collections import Counter
from typing import Any

POLICY_TOPICS = (
    "城市更新",
    "低效用地",
    "存量空间",
    "存量盘活",
    "城市更新",
    "低效用地",
    "存量空间",
    "存量盘活",
    "国土空间开发保护",
    "三条控制线",
    "永久基本农田",
    "生态保护红线",
    "土地节约集约利用",
    "产业空间",
    "交通与城镇布局",
    "城市发展方向",
    "规划实施",
)


def build_report_evidence(
    analysis_payload: dict[str, Any],
    policy_documents: list[dict[str, Any]],
    dataset_name: str,
) -> dict[str, Any]:
    decisions = list(analysis_payload.get("decisions") or [])
    candidates = [item for item in decisions if item.get("block_id") is not None]
    counts = Counter(str(item.get("decision") or "未分类") for item in decisions)
    sorted_candidates = sorted(
        candidates,
        key=lambda item: float(
            item.get("priority_score")
            or item.get("dynamic_score")
            or item.get("overall_suitability")
            or 0
        ),
        reverse=True,
    )
    return {
        "region": _guess_region(dataset_name, decisions),
        "dataset_name": dataset_name,
        "analysis_summary": {
            "total_blocks": len(decisions),
            "priority_regeneration": counts.get("重点再生", 0),
            "incremental_renewal": counts.get("渐进更新", 0),
            "vitality_cultivation": counts.get("活力培育", 0),
            "stable_improvement": counts.get("稳定提升", 0),
            "ecological_restoration": counts.get("生态修复", 0),
            "manual_review": sum(bool(item.get("manual_review_required")) for item in decisions),
            "counts": dict(counts),
        },
        "candidate_blocks": [_candidate_item(item) for item in sorted_candidates[:80]],
        "policy_evidence": _policy_evidence(policy_documents),
    }


def _candidate_item(item: dict[str, Any]) -> dict[str, Any]:
    drivers = list(
        item.get("key_evidence") or item.get("key_drivers") or item.get("key_reasons") or []
    )
    risks = list(item.get("risks") or [])
    return {
        "block_id": str(item.get("block_id") or ""),
        "block_name": item.get("block_name"),
        "district": item.get("district") or item.get("行政区") or item.get("区县") or "",
        "area": item.get("area") or item.get("面积") or item.get("Shape_Area"),
        "inefficiency_score": item.get("inefficiency_score") or item.get("overall_suitability"),
        "regeneration_potential": item.get("regeneration_potential")
        or item.get("development_probability"),
        "priority_score": item.get("priority_score") or item.get("dynamic_score"),
        "planning_match": item.get("planning_match"),
        "constraint_cost": item.get("constraint_cost"),
        "dynamic_score": item.get("dynamic_score"),
        "decision": str(item.get("regeneration_scenario") or item.get("decision") or ""),
        "scenario_actions": list(item.get("scenario_actions") or []),
        "implementation_timing": item.get("implementation_timing"),
        "positive_factors": [{"name": str(value), "value": None} for value in drivers[:4]],
        "negative_factors": [{"name": str(value), "value": None} for value in risks[:4]],
        "constraints": {
            "ecological_redline": _has_keyword(risks, "生态"),
            "permanent_farmland": _has_keyword(risks, "农田"),
            "hazard": _has_keyword(risks, "灾害"),
        },
    }


def _policy_evidence(policy_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for doc in policy_documents:
        text = str(doc.get("text") or "")
        if not text:
            continue
        for topic in POLICY_TOPICS:
            index = text.find(topic)
            if index < 0:
                continue
            start = max(0, index - 120)
            end = min(len(text), index + 420)
            evidence.append(
                {
                    "source": str(doc.get("name") or "政策参考文档"),
                    "article": "",
                    "page": None,
                    "topic": topic,
                    "content": text[start:end].replace("\n", " ").strip(),
                }
            )
            if len(evidence) >= 12:
                return evidence
    return evidence


def _guess_region(dataset_name: str, decisions: list[dict[str, Any]]) -> str:
    for item in decisions:
        district = item.get("district") or item.get("行政区") or item.get("区县")
        if district:
            return f"武汉市{district}" if "武汉" not in str(district) else str(district)
    if "武汉" in dataset_name:
        return "武汉市"
    return "武汉市"


def _has_keyword(values: list[Any], keyword: str) -> bool:
    return any(keyword in str(value) for value in values)
