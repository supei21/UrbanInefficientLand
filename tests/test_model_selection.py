from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tianshu_core.llm.client import (
    build_chat_model,
    get_default_model_id,
    get_model_settings,
    list_model_options,
)


class ModelSelectionTest(unittest.TestCase):
    def test_local_rules_are_always_available(self):
        option = next(item for item in list_model_options() if item["id"] == "local-rules")
        self.assertTrue(option["ready"])
        self.assertEqual(option["kind"], "local")
        self.assertFalse(get_model_settings("local-rules")["enabled"])

    def test_default_model_id_is_selectable(self):
        options = list_model_options()
        default_id = get_default_model_id()
        self.assertTrue(any(item["id"] == default_id and item["ready"] for item in options))

    def test_unknown_model_is_not_resolved(self):
        with self.assertRaises(KeyError):
            get_model_settings("not-configured")

    @patch("langchain_openai.ChatOpenAI")
    def test_kimi_uses_provider_temperature_default(self, chat_open_ai: MagicMock):
        build_chat_model(
            {
                "enabled": True,
                "model": "kimi-k3",
                "base_url": "https://api.moonshot.cn/v1",
                "api_key": "sk-test",
            }
        )

        kwargs = chat_open_ai.call_args.kwargs
        self.assertNotIn("temperature", kwargs)
        self.assertEqual(kwargs["model"], "kimi-k3")
        self.assertEqual(kwargs["base_url"], "https://api.moonshot.cn/v1")

    @patch("langchain_openai.ChatOpenAI")
    def test_non_kimi_keeps_configured_temperature(self, chat_open_ai: MagicMock):
        build_chat_model(
            {
                "enabled": True,
                "model": "glm-5.3-flash",
                "base_url": "https://open.bigmodel.cn/api/paas/v4/",
                "api_key": "sk-test",
                "temperature": 0.2,
            }
        )

        self.assertEqual(chat_open_ai.call_args.kwargs["temperature"], 0.2)


if __name__ == "__main__":
    unittest.main()
