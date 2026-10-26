from __future__ import annotations

import unittest
from unittest.mock import patch

from tianshu_core.config import load_config
from tianshu_core.models import BlockInput
from tianshu_core.rag.policy_client import assess_block_with_rag, assess_blocks_with_rag
from tianshu_core.workflow.rules import check_constraints


class PolicyRagTest(unittest.TestCase):
    def test_import_farmland_block_is_rejected_by_policy_rule(self):
        config = load_config()
        block = BlockInput(
            block_id="RAG_TEST_001",
            inside_boundary=False,
            permanent_farmland=True,
            ecological_redline=False,
            prohibited_disaster_zone=False,
            disaster_risk="低",
            planning_match=80,
            development_probability=90,
        )

        assessment = assess_block_with_rag(block, config)
        self.assertTrue(assessment.available)
        self.assertEqual(assessment.rules["suggested_action"], "禁止调入")
        self.assertIn("R077", [rule["rule_id"] for rule in assessment.rules["matched_rules"]])
        self.assertGreaterEqual(len(assessment.retrieval["sources"]), 1)

    def test_constraint_result_carries_policy_evidence(self):
        config = load_config()
        block = BlockInput(
            block_id="RAG_TEST_002",
            inside_boundary=False,
            permanent_farmland=True,
            ecological_redline=False,
            prohibited_disaster_zone=False,
            disaster_risk="低",
        )

        result = check_constraints(block, config)
        self.assertTrue(result.hard_constraint)
        self.assertTrue(result.policy_rag_available)
        self.assertEqual(result.policy_assessment, "禁止调入")
        self.assertEqual(result.policy_compliance, "不符合")
        self.assertTrue(result.policy_matched_rules)
        self.assertTrue(result.policy_sources)

    def test_inclusion_only_rule_does_not_block_exclusion(self):
        block = BlockInput(
            block_id="inside-high-risk",
            inside_boundary=True,
            disaster_risk="高",
            ecological_redline=False,
            permanent_farmland=False,
            prohibited_disaster_zone=False,
        )

        result = check_constraints(block, load_config())

        self.assertFalse(result.hard_constraint)
        self.assertNotIn("R001", [item.get("rule_id") for item in result.policy_matched_rules])

    def test_batch_rag_reuses_retrieval_for_same_policy_signature(self):
        blocks = [
            BlockInput(
                block_id=f"same-policy-{index}",
                inside_boundary=False,
                permanent_farmland=False,
                ecological_redline=False,
                prohibited_disaster_zone=False,
                disaster_risk="低",
                dominant_landuse="建设用地",
                planning_match=75,
            )
            for index in range(5)
        ]
        calls = []

        def fake_search(query, settings, k=None):
            calls.append(query)
            return [
                {
                    "source": "policy.docx",
                    "type": "policy",
                    "score": 1.0,
                    "rule_id": None,
                    "article_ref": "测试条款",
                    "content": "测试政策依据",
                }
            ]

        with patch("tianshu_core.rag.evaluator.search_policy_documents", side_effect=fake_search):
            results = assess_blocks_with_rag(blocks, load_config())

        self.assertEqual(len(results), 5)
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(item.available for item in results.values()))

    def test_positive_policy_rule_and_complete_baseline_is_compliant(self):
        block = BlockInput(
            block_id="policy-positive",
            inside_boundary=False,
            ecological_redline=False,
            permanent_farmland=False,
            prohibited_disaster_zone=False,
            disaster_risk="低",
            planning_match=80,
            scenario="国家和省重大战略实施或重大项目建设",
        )

        result = check_constraints(block, load_config())

        self.assertEqual(result.policy_compliance, "符合")
        self.assertIn("R003", [item.get("rule_id") for item in result.policy_matched_rules])

    def test_missing_policy_facts_cannot_be_reported_as_compliant(self):
        block = BlockInput(
            block_id="policy-incomplete",
            inside_boundary=False,
            planning_match=80,
            scenario="国家和省重大战略实施或重大项目建设",
        )

        result = check_constraints(block, load_config())

        self.assertEqual(result.policy_compliance, "有条件符合")
        self.assertTrue(result.policy_requirements)


if __name__ == "__main__":
    unittest.main()
