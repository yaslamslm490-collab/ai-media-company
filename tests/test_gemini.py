from __future__ import annotations

import json
import urllib.error
import unittest
from unittest.mock import Mock

from backend.gemini import GeminiAdapter, GeminiNotConfigured, GeminiRequestFailed


class FakeResponse:
    def __init__(self, payload: object):
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return self.raw


class GeminiAdapterTests(unittest.TestCase):
    def test_configuration_requires_server_key_and_model_without_network(self):
        with self.assertRaises(GeminiNotConfigured):
            GeminiAdapter.from_env({})
        key = "mock" + "-credential"
        with self.assertRaises(GeminiNotConfigured):
            GeminiAdapter.from_env({"GEMINI_API_KEY": key})

    def test_success_uses_openai_compatible_shape_and_never_returns_key(self):
        opener = Mock(return_value=FakeResponse({"choices": [{"message": {"content": "رد Gemini محلي."}}]}))
        key = "mock" + "-credential"
        adapter = GeminiAdapter.from_env({"GEMINI_API_KEY": key, "GEMINI_MODEL": "gemini-test-model"}, opener=opener)
        result = adapter.chat("اكتب رداً قصيراً", system_prompt="أجب بالعربية.")
        request = opener.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(result, {"response": "رد Gemini محلي.", "model": "gemini-test-model"})
        self.assertEqual(request.full_url, "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {key}")
        self.assertEqual(payload["model"], "gemini-test-model")
        self.assertNotIn(key, json.dumps(result, ensure_ascii=False))

    def test_chat_preserves_conversation_context(self):
        opener = Mock(return_value=FakeResponse({"choices": [{"message": {"content": "رد سياقي"}}]}))
        adapter = GeminiAdapter.from_env({"GEMINI_API_KEY": "mock-credential", "GEMINI_MODEL": "gemini-test-model"}, opener=opener)
        history = [
            {"role": "user", "content": "اسمي سلمى"},
            {"role": "assistant", "content": "أهلًا سلمى"},
            {"role": "user", "content": "ما اسمي؟"},
        ]
        adapter.chat(history, system_prompt="أجب بالعربية.")
        payload = json.loads(opener.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["messages"][1:], history)

    def test_http_failure_is_safe_and_does_not_expose_key(self):
        key = "mock" + "-credential-secret"
        opener = Mock(side_effect=urllib.error.URLError("offline"))
        adapter = GeminiAdapter.from_env({"GEMINI_API_KEY": key, "GEMINI_MODEL": "gemini-test-model"}, opener=opener)
        with self.assertRaises(GeminiRequestFailed) as raised:
            adapter.chat("اختبار")
        self.assertEqual(str(raised.exception), "تعذّر الاتصال بخدمة Gemini.")
        self.assertNotIn(key, str(raised.exception))

    def test_invalid_response_is_rejected_without_claiming_success(self):
        opener = Mock(return_value=FakeResponse({"choices": []}))
        adapter = GeminiAdapter.from_env({"GEMINI_API_KEY": "mock" + "-credential", "GEMINI_MODEL": "gemini-test-model"}, opener=opener)
        with self.assertRaisesRegex(GeminiRequestFailed, "لم يُعِد Gemini نصاً صالحاً"):
            adapter.chat("اختبار")


if __name__ == "__main__":
    unittest.main()
