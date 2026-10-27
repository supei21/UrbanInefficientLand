"""Conversation service for the competition's low-efficiency regeneration workflow."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from tianshu_core.agent.events import EventCallback, emit

AnalysisProvider = Callable[[], dict[str, Any] | None]
AnalysisRunner = Callable[[], dict[str, Any]]


class RegenerationChatResult(BaseModel):
    """Transport-neutral result consumed by the streaming API."""

    response: str
    selected_block_ids: list[str] = Field(default_factory=list)
    block_records: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    workflow_summary: dict[str, Any] = Field(default_factory=dict)
    model_used: bool = False
    warnings: list[str] = Field(default_factory=list)


def _help_answer(block_count: int) -> str:
    return (
        f"当前工作区已加载 {block_count} 个空间单元。系统围绕“低效程度 × 再生潜力”完成四类任务：\n\n"
        "1. 低效识别：从土地利用、城市活力、功能结构、公共服务、交通可达性和空间品质六个维度计算低效程度，并划分四级。\n"
        "2. 潜力评估：综合区位价值、市场支撑、空间容量和实施可行性，形成再生潜力与优先级。\n"
        "3. 场景策划：将空间单元归入重点再生、渐进更新、活力培育、稳定提升或生态修复，并给出行动建议和实施时序。\n"
        "4. 结果解释：可继续询问优先片区、主要驱动因素、风险、政策核验重点和单元详情。\n\n"
        "推荐流程：先在“再生分析”运行识别，再回到这里询问“最优先的更新片区有哪些”或“解释重点单元的驱动因素”。"
    )


def _matched_decisions(query: str, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in decisions:
        block_id = str(item.get("block_id") or "")
        district = str(item.get("district") or "")
        id_matched = bool(
            block_id and re.search(rf"(?<![0-9A-Za-z]){re.escape(block_id)}(?![0-9A-Za-z])", query)
        )
        if id_matched or (district and district in query):
            matches.append(item)
    return matches


def _analysis_answer(query: str, payload: dict[str, Any]) -> tuple[str, list[str]]:
    summary = payload.get("summary") or {}
    decisions = list(payload.get("decisions") or [])
    matched = _matched_decisions(query, decisions)
    selected = matched or decisions[:5]
    scenario_counts = summary.get("scenario_counts") or {}
    scenario_text = "、".join(f"{name} {count} 个" for name, count in scenario_counts.items())

    lines = [
        (
            f"已完成 {summary.get('total', len(decisions))} 个空间单元的低效空间再生分析。"
            f"识别低效候选 {summary.get('candidate_count', 0)} 个，近期重点 "
            f"{summary.get('priority_count', 0)} 个，需人工复核 {summary.get('manual_review_count', 0)} 个。"
        ),
        (
            f"整体平均低效程度为 {summary.get('average_inefficiency', 0):.1f}，"
            f"平均再生潜力为 {summary.get('average_potential', 0):.1f}。"
        ),
    ]
    if scenario_text:
        lines.append(f"场景分布：{scenario_text}。")

    if matched:
        lines.append("你提到的空间单元如下：")
    elif any(word in query for word in ("优先", "重点", "最高", "片区", "哪些")):
        lines.append("综合优先级最高的空间单元如下：")
    else:
        lines.append("以下为综合优先级前五的空间单元：")

    for item in selected[:8]:
        evidence = "、".join(item.get("key_evidence") or []) or "需补充基础数据"
        actions = "、".join(item.get("scenario_actions") or [])
        lines.append(
            f"• {item.get('block_id')}（{item.get('district') or item.get('block_name') or '未命名'}）："
            f"{item.get('regeneration_scenario')}，低效 {item.get('inefficiency_score', 0):.1f}，"
            f"潜力 {item.get('regeneration_potential', 0):.1f}，优先级 {item.get('priority_score', 0):.1f}。"
            f"主要依据：{evidence}；建议：{actions}。"
        )

    if any(word in query for word in ("风险", "政策", "依据", "合规")):
        lines.append(
            "政策与实施核验重点：生态保护红线、永久基本农田、灾害风险、权属、法定规划用途和项目资金条件必须在实施前逐项复核。"
        )
    lines.append(str(payload.get("disclaimer") or "结果仅用于竞赛研究和项目初筛。"))
    return "\n\n".join(lines), [str(item.get("block_id")) for item in selected[:8]]


def handle_regeneration_chat(
    query: str,
    blocks: list[dict[str, Any]],
    *,
    analysis_provider: AnalysisProvider,
    analysis_runner: AnalysisRunner,
    event_callback: EventCallback | None = None,
) -> RegenerationChatResult:
    """Answer from the regeneration domain without invoking the legacy boundary workflow."""

    emit(event_callback, "understand", "理解任务", "识别低效空间再生分析需求")
    if any(word in query for word in ("怎么用", "帮助", "能做什么", "操作流程", "介绍")):
        emit(
            event_callback,
            "answer",
            "整理系统能力",
            "生成低效识别、潜力评估和场景策划操作说明",
            status="completed",
        )
        return RegenerationChatResult(response=_help_answer(len(blocks)))

    emit(
        event_callback,
        "action",
        "读取空间单元",
        f"当前工作区包含 {len(blocks)} 个空间单元",
        status="completed",
    )
    payload = analysis_provider()
    if payload is None:
        emit(
            event_callback,
            "action",
            "运行再生分析",
            "计算低效程度、再生潜力、优先级和五类场景",
        )
        payload = analysis_runner()
        emit(
            event_callback,
            "observe",
            "完成再生分析",
            f"已完成 {payload.get('summary', {}).get('total', len(blocks))} 个空间单元",
            status="completed",
        )
    else:
        emit(
            event_callback,
            "observe",
            "复用最新分析",
            "读取最近一次低效空间识别与场景策划结果",
            status="completed",
        )

    response, selected_ids = _analysis_answer(query, payload)
    emit(
        event_callback,
        "answer",
        "生成规划答复",
        "基于可追溯指标和场景建议形成回答",
        status="completed",
    )
    return RegenerationChatResult(
        response=response,
        selected_block_ids=selected_ids,
        workflow_summary=dict(payload.get("summary") or {}),
    )
