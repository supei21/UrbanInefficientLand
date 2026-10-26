from __future__ import annotations

import unittest

from tianshu_core.llm.policy_response import format_policy_answer, is_policy_query


class PolicyResponseTest(unittest.TestCase):
    def test_policy_query_detection(self):
        self.assertTrue(is_policy_query("这个地块是否符合政策规定？"))
        self.assertFalse(is_policy_query("显示地块原始属性"))

    def test_conditional_inclusion_uses_auditable_sections(self):
        response = format_policy_answer(
            "该地块是否可以调入？",
            [
                {
                    "block_id": "WH001",
                    "block_name": "测试地块",
                    "inside_boundary": False,
                    "decision": "二级优先调入",
                    "overall_suitability": 78.3,
                    "development_probability": 86.4,
                    "planning_match": 72.0,
                    "constraint_status": "约束信息待核验",
                    "policy_compliance": "有条件符合",
                    "policy_reason": "已命中程序性条款，须完成前置核验。",
                    "policy_requirements": ["核实是否涉及永久基本农田。"],
                    "missing_information": ["补充项目类型。"],
                    "key_drivers": ["交通可达性较高"],
                    "risks": [],
                    "policy_matched_rules": [
                        {
                            "rule_id": "R010",
                            "policy_name": "城镇开发边界管理办法",
                            "article_ref": "第十条",
                            "action": "符合条件后可作为调入候选",
                            "source_text": "依法依规开展局部优化。",
                            "score_adjustment": 0.2,
                        }
                    ],
                    "policy_sources": [
                        {
                            "source": "政策法规/城镇开发边界管理办法（试行）.pdf",
                            "type": "policy",
                            "score": 0.8123,
                            "excerpt": "城镇开发边界可按规定开展局部优化。",
                        }
                    ],
                }
            ],
            1,
        )
        self.assertIn("满足前置条件后可进入调入综合评价", response)
        self.assertIn("## 地块事实", response)
        self.assertIn("## 适用政策依据", response)
        self.assertIn("## 匹配的政策文件", response)
        self.assertIn("城镇开发边界管理办法（试行）.pdf", response)
        self.assertIn("RAG相关度 0.812", response)
        self.assertIn("## 禁止性约束", response)
        self.assertIn("## 仍需核验", response)

    def test_direction_mismatch_is_not_rewritten_as_opposite_permission(self):
        response = format_policy_answer(
            "这个地块是否允许调入？",
            [
                {
                    "block_id": "WH002",
                    "inside_boundary": True,
                    "decision": "保持现状",
                    "constraint_status": "未发现硬约束",
                    "policy_compliance": "符合",
                    "policy_reason": "命中正向政策情形。",
                }
            ],
            1,
        )
        self.assertIn("政策可行性结论：不适用调入判读", response)
        self.assertIn("地块当前位于城镇开发边界内", response)
        self.assertNotIn("允许进入调出综合评价", response)

    def test_supporting_rule_cannot_override_blocking_constraint(self):
        response = format_policy_answer(
            "这个地块符合政策吗？",
            [
                {
                    "block_id": "WH003",
                    "inside_boundary": False,
                    "decision": "人工复核",
                    "constraint_status": "存在硬约束",
                    "policy_compliance": "不符合",
                    "policy_reason": "已命中禁止性政策规则。",
                    "risks": ["涉及生态保护红线"],
                    "policy_matched_rules": [
                        {
                            "rule_id": "R001",
                            "policy_name": "生态保护规则",
                            "action": "禁止调入",
                            "score_adjustment": -1.0,
                        },
                        {
                            "rule_id": "R002",
                            "policy_name": "项目支持规则",
                            "action": "重大项目可作为调入候选",
                            "score_adjustment": 0.3,
                        },
                    ],
                }
            ],
            1,
        )
        self.assertIn("禁止进入调入综合评价", response)
        self.assertIn("涉及生态保护红线", response)
        self.assertIn("支持性依据不能覆盖已命中的禁止性约束", response)

    def test_multiple_insufficient_results_show_gate_sections_and_files(self):
        response = format_policy_answer(
            "候选地块是否符合调入政策？",
            [
                {
                    "block_id": "WH101",
                    "inside_boundary": False,
                    "decision": "一级优先调入",
                    "constraint_status": "约束信息待核验",
                    "policy_compliance": "依据不足",
                    "policy_requirements": ["核实是否涉及永久基本农田。"],
                    "missing_information": ["补充项目类型。"],
                    "policy_sources": [
                        {
                            "source": "城镇开发边界管理办法（试行）.pdf",
                            "type": "policy",
                            "score": 0.71,
                            "excerpt": "严格城镇开发边界管控。",
                        }
                    ],
                },
                {
                    "block_id": "WH102",
                    "inside_boundary": False,
                    "decision": "二级优先调入",
                    "constraint_status": "约束信息待核验",
                    "policy_compliance": "依据不足",
                    "policy_requirements": ["核实是否涉及生态保护红线。"],
                    "missing_information": ["补充调整情形。"],
                    "policy_sources": [
                        {
                            "source": "城镇开发边界管理办法（试行）.pdf",
                            "type": "policy",
                            "score": 0.68,
                            "excerpt": "严格城镇开发边界管控。",
                        }
                    ],
                },
            ],
            2,
        )
        self.assertIn("暂不认定为合规调入候选", response)
        self.assertIn("## 禁止性约束", response)
        self.assertIn("## 限制性条件", response)
        self.assertIn("## 允许/支持条件", response)
        self.assertIn("## 仍需核验", response)
        self.assertIn("## 匹配的政策文件", response)
        self.assertEqual(response.count("城镇开发边界管理办法（试行）.pdf"), 1)


if __name__ == "__main__":
    unittest.main()
