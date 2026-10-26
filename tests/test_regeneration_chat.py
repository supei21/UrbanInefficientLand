from __future__ import annotations

import unittest

from tianshu_core.regeneration_chat import handle_regeneration_chat


class RegenerationChatTest(unittest.TestCase):
    def test_help_does_not_run_analysis(self):
        calls = []
        result = handle_regeneration_chat(
            "介绍系统操作流程",
            [{"object_id": 1}],
            analysis_provider=lambda: None,
            analysis_runner=lambda: calls.append(True),
        )

        self.assertEqual(calls, [])
        self.assertIn("低效识别", result.response)

    def test_analysis_answer_uses_latest_regeneration_payload(self):
        events = []
        payload = {
            "summary": {
                "total": 1,
                "candidate_count": 1,
                "priority_count": 1,
                "manual_review_count": 0,
                "average_inefficiency": 82.0,
                "average_potential": 76.0,
                "scenario_counts": {"重点再生": 1},
            },
            "decisions": [
                {
                    "block_id": "A01",
                    "district": "示范区",
                    "regeneration_scenario": "重点再生",
                    "inefficiency_score": 82.0,
                    "regeneration_potential": 76.0,
                    "priority_score": 100.0,
                    "key_evidence": ["活力不足 81.0"],
                    "scenario_actions": ["公共空间织补"],
                }
            ],
            "disclaimer": "仅用于测试。",
        }

        result = handle_regeneration_chat(
            "最优先的更新片区有哪些",
            [{"object_id": 1}],
            analysis_provider=lambda: payload,
            analysis_runner=lambda: self.fail("不应重复运行分析"),
            event_callback=events.append,
        )

        self.assertIn("A01", result.response)
        self.assertEqual(result.selected_block_ids, ["A01"])
        self.assertTrue(any(event.title == "复用最新分析" for event in events))


if __name__ == "__main__":
    unittest.main()
