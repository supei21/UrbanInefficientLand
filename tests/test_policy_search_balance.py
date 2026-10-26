from __future__ import annotations

import unittest

from tianshu_core.rag.vector_store import _select_balanced_results


def indexed_document(source: str, item_type: str) -> dict:
    return {
        "content": source,
        "metadata": {"source": source, "type": item_type},
        "embedding": [1.0, 0.0],
    }


class PolicySearchBalanceTest(unittest.TestCase):
    def test_policy_files_are_not_crowded_out_by_rules(self):
        scored = [
            (1.00 - index * 0.01, indexed_document(f"rule-{index}", "rule")) for index in range(10)
        ]
        scored.extend(
            [
                (0.70, indexed_document("城镇开发边界管理办法.pdf", "policy")),
                (0.69, indexed_document("武汉市国土空间总体规划.pdf", "policy")),
                (0.68, indexed_document("全域土地综合整治实施指南.docx", "policy")),
            ]
        )

        selected = _select_balanced_results(scored, 6)

        policy_sources = [
            item["metadata"]["source"]
            for _, item in selected
            if item["metadata"]["type"] == "policy"
        ]
        self.assertEqual(len(selected), 6)
        self.assertEqual(len(policy_sources), 3)
        self.assertIn("城镇开发边界管理办法.pdf", policy_sources)

    def test_duplicate_chunks_do_not_replace_distinct_policy_files(self):
        shared = indexed_document("同一政策.pdf", "policy")
        duplicate = indexed_document("同一政策.pdf", "policy")
        scored = [
            (0.9, shared),
            (0.89, duplicate),
            (0.88, indexed_document("另一政策.pdf", "policy")),
            (0.87, indexed_document("rule-1", "rule")),
            (0.86, indexed_document("rule-2", "rule")),
        ]

        selected = _select_balanced_results(scored, 4)
        policy_sources = [
            item["metadata"]["source"]
            for _, item in selected
            if item["metadata"]["type"] == "policy"
        ]
        self.assertEqual(policy_sources.count("同一政策.pdf"), 1)
        self.assertIn("另一政策.pdf", policy_sources)


if __name__ == "__main__":
    unittest.main()
