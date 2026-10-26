from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from report.document_schema import (
    PlanningPolicyDocument,
    ReportArticle,
    ReportChapter,
    ReportSection,
)
from tianshu_core.llm.client import build_chat_model, get_api_key

REPORT_TITLE = "城市低效空间再生识别与场景策划报告"
SYSTEM_PROMPT = f"""
你负责生成城市更新与国土空间规划研究文本。
请根据空间分析结果和政策检索依据，形成正式、严谨、内容充实的研究正文。
只能使用输入中真实存在的数据，不得修改评价结果、场景分类和空间约束结果。
不得编造政策、政策条文或审批结论，政策依据只能来自policy_evidence。
采用“章—节—条—正文”的结构，围绕低效空间识别、综合评价、约束核验、
再生场景、行动时序和实施保障展开。报告标题必须为“{REPORT_TITLE}”。
技术信息应转写为自然的规划语言，不直接出现模型或算法名称。
不要输出Markdown，严格输出指定JSON。
""".strip()

FORBIDDEN_TERMS = (
    "智能体",
    "人工智能",
    "AI",
    "DeepSeek",
    "大模型",
    "Demo",
    "系统生成",
    "模型自动生成",
    "XGBoost",
    "SHAP",
    "机器学习",
    "算法",
    "特征重要性",
)


def generate_policy_document(
    evidence: dict[str, Any], model_settings: dict[str, Any] | None
) -> tuple[PlanningPolicyDocument, bool, str | None]:
    if model_settings and model_settings.get("enabled") and get_api_key(model_settings):
        try:
            llm = build_chat_model({**model_settings, "temperature": 0.2, "max_tokens": 8500})
            response = llm.invoke(_build_prompt(evidence))
            return _sanitize(_parse(str(getattr(response, "content", response)))), True, None
        except (ValidationError, ValueError, json.JSONDecodeError, TypeError) as exc:
            return _fallback(evidence), False, f"文本结构不合法，已使用本地模板：{exc}"
        except Exception as exc:
            return _fallback(evidence), False, f"文本生成失败，已使用本地模板：{exc}"
    return _fallback(evidence), False, None


def _build_prompt(evidence: dict[str, Any]) -> str:
    schema = {
        "title": REPORT_TITLE,
        "preface": "前言正文",
        "chapters": [
            {
                "title": "第一章  识别说明",
                "sections": [{"articles": [{"title": "第1条  研究背景", "content": "条文正文"}]}],
            }
        ],
    }
    return (
        f"{SYSTEM_PROMPT}\n\n输出JSON格式：\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        "至少生成5章、22条；前三章为识别说明、政策依据、场景策划。"
        "每条使用完整自然段，不插入图片、项目符号或技术模型名称。\n\n"
        f"Evidence：\n{json.dumps(evidence, ensure_ascii=False)[:18000]}"
    )


def _parse(text: str) -> PlanningPolicyDocument:
    cleaned = text.strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.S)
    return PlanningPolicyDocument.model_validate_json(match.group(0) if match else cleaned)


def _article(number: int, title: str, content: str) -> tuple[str, str]:
    return f"第{number}条  {title}", content


def _fallback(evidence: dict[str, Any]) -> PlanningPolicyDocument:
    region = str(evidence.get("region") or "武汉市")
    summary = dict(evidence.get("analysis_summary") or {})
    candidates = list(evidence.get("candidate_blocks") or [])
    policy = list(evidence.get("policy_evidence") or [])
    top_names = "、".join(str(item.get("block_id")) for item in candidates[:6]) or "暂无重点单元"
    sources = (
        "、".join(
            dict.fromkeys(str(item.get("source")) for item in policy[:6] if item.get("source"))
        )
        or "现有政策参考材料"
    )
    total = summary.get("total_blocks", 0)
    priority = summary.get("priority_regeneration", 0)
    gradual = summary.get("incremental_renewal", 0)
    cultivate = summary.get("vitality_cultivation", 0)
    chapters = [
        (
            "第一章  识别说明",
            [
                _article(
                    1,
                    "研究背景",
                    f"面向{region}存量提质与城市活力重塑需求，本报告识别活力不足、功能失配、空间衰退和可达性短板，并评估其再生潜力。",
                ),
                _article(
                    2,
                    "研究目标",
                    "建立可解释、可复核的低效空间识别与分类体系，将分析结论转化为可执行的场景策划、行动时序和项目清单。",
                ),
                _article(
                    3,
                    "研究对象",
                    f"本次共分析{total}个空间单元，其中重点再生{priority}个、渐进更新{gradual}个、活力培育{cultivate}个。重点关注单元包括{top_names}。",
                ),
                _article(
                    4,
                    "识别逻辑",
                    "综合活力、功能、空间品质、交通可达、区位价值、市场支撑、空间承载和实施可行性，形成低效程度与再生潜力二维分类。",
                ),
                _article(
                    5,
                    "成果边界",
                    "本报告用于竞赛研究、项目初筛和方案沟通，不替代法定规划、权属核验、公众参与、工程可行性论证及行政审批。",
                ),
            ],
        ),
        (
            "第二章  政策依据",
            [
                _article(
                    6,
                    "依据来源",
                    f"报告结合空间分析成果和政策检索材料编制，参考来源包括{sources}，引用时应保持来源可追溯。",
                ),
                _article(
                    7,
                    "城市更新导向",
                    "坚持存量优先、节约集约和以人为本，优先盘活闲置低效空间，补齐公共服务短板，改善人居环境并激发在地经济。",
                ),
                _article(
                    8,
                    "底线约束",
                    "涉及生态保护红线、永久基本农田、灾害风险、河湖水系和重大基础设施廊道的单元，应先行开展图斑级核验。",
                ),
                _article(
                    9,
                    "规划衔接",
                    "再生场景应与总体规划、详细规划和专项规划衔接，统筹功能布局、交通组织、公共服务、历史文化保护和蓝绿网络。",
                ),
                _article(
                    10,
                    "实施监督",
                    "分类建议进入实施阶段后，应建立项目台账、责任主体、资金路径和动态监测机制，确保研究结论在复核后有序转化。",
                ),
            ],
        ),
        (
            "第三章  场景策划",
            [
                _article(
                    11,
                    "重点再生",
                    "对高低效、高潜力单元，优先导入复合功能，开展存量建筑适应性再利用、公共空间织补和慢行交通改善。",
                ),
                _article(
                    12,
                    "渐进更新",
                    "对问题突出但实施条件有限的单元，采用低成本、分阶段方式推进安全整治、小微公共空间提升和基础设施补短板。",
                ),
                _article(
                    13,
                    "活力培育",
                    "对现状基础较好且具有提升机会的单元，通过社区服务嵌入、首层界面激活、特色业态导入和公共活动运营增强使用强度。",
                ),
                _article(
                    14,
                    "稳定提升",
                    "对低效程度和再生潜力均较低的单元，以常态维护、生活圈补缺和低扰动环境改善为主，避免不必要的大拆大建。",
                ),
                _article(
                    15,
                    "生态修复",
                    "对受刚性约束影响的单元，坚持保护和修复优先，开展污染治理、风险消减、建设活动退出及蓝绿网络修复。",
                ),
            ],
        ),
        (
            "第四章  行动时序与保障",
            [
                _article(
                    16,
                    "近期行动",
                    "近期优先选择权属相对清晰、需求明确、公共效益突出且实施条件成熟的重点再生单元，形成示范成果。",
                ),
                _article(
                    17,
                    "中期储备",
                    "中期项目重点完成详细策划、设施承载评估、资金测算和多方协商，待约束与实施条件成熟后分批启动。",
                ),
                _article(
                    18,
                    "部门协同",
                    "建立规划、住建、自然资源、生态环境、交通、水务和属地政府协同复核机制，形成闭环意见。",
                ),
                _article(
                    19,
                    "投融资组织",
                    "根据公益性、经营性和混合性项目特征匹配财政投入、社会资本和运营收益，防止策划目标与后续运营脱节。",
                ),
            ],
        ),
        (
            "第五章  结论与动态维护",
            [
                _article(
                    20,
                    "总体结论",
                    "低效空间再生应从单一物质改造转向活力、功能、品质与治理协同提升，并以二维分类支撑差异化施策。",
                ),
                _article(
                    21,
                    "应用建议",
                    "建议将识别图件、候选单元清单、场景卡片、政策依据和实施时序配套使用，优先开展现场核查与方案深化。",
                ),
                _article(
                    22,
                    "动态监测",
                    "结合人口活动、业态变化、建设状态、公共服务和生态约束的更新，定期重算评价结果并记录场景调整原因。",
                ),
            ],
        ),
    ]
    return PlanningPolicyDocument(
        title=REPORT_TITLE,
        preface=f"为支撑{region}低效空间识别、城市活力重塑和再生项目策划，依据现有空间分析结果与政策检索材料形成本报告。",
        chapters=[
            ReportChapter(
                title=chapter_title,
                sections=[
                    ReportSection(
                        articles=[
                            ReportArticle(title=title, content=content)
                            for title, content in articles
                        ]
                    )
                ],
            )
            for chapter_title, articles in chapters
        ],
    )


def _sanitize(document: PlanningPolicyDocument) -> PlanningPolicyDocument:
    data = document.model_dump()

    def clean(value: str) -> str:
        for term in FORBIDDEN_TERMS:
            value = value.replace(term, "综合评价")
        return value

    data["title"] = REPORT_TITLE
    data["preface"] = clean(data.get("preface") or "")
    for chapter in data["chapters"]:
        chapter["title"] = clean(chapter["title"])
        for section in chapter["sections"]:
            for article in section["articles"]:
                article["title"] = clean(article["title"])
                article["content"] = clean(article["content"])
    return PlanningPolicyDocument.model_validate(data)
