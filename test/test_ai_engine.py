import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.ai_engine import AIEngine
from src.config_parser import config


class _FailingCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        raise Exception("This model's context length was exceeded by the prompt.")


class _FakeClient:
    def __init__(self):
        self.completions = _FailingCompletions()
        self.chat = self


class _ResponseCompletions:
    def __init__(self, contents):
        self.contents = iter(contents)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        content = next(self.contents)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class _ResponseClient:
    def __init__(self, contents):
        self.completions = _ResponseCompletions(contents)
        self.chat = self


class _StructuredContextError(Exception):
    body = {"error": {"code": "exceed_context_size_error"}}


class TestAIEngine(unittest.TestCase):
    def test_context_limit_error_does_not_retry(self):
        engine = AIEngine()
        fake_client = _FakeClient()
        engine.client = fake_client

        result, _ = engine._get_json_response([{"role": "user", "content": "x"}])

        self.assertEqual("ERROR", result["status"])
        self.assertIn("context limit", result["reason"].lower())
        self.assertEqual(1, fake_client.completions.calls)

    def test_structured_context_error_is_detected(self):
        self.assertTrue(
            AIEngine._is_context_limit_error(
                _StructuredContextError("request exceeds the available context size")
            )
        )

    def test_invalid_schema_is_retried_until_valid(self):
        engine = AIEngine()
        fake_client = _ResponseClient(
            [
                '{"status":"MAYBE","reason":"no"}',
                '{"status":"SAFE","reason":"valid"}',
            ]
        )
        engine.client = fake_client

        result, log = engine._get_json_response([{"role": "user", "content": "x"}])

        self.assertEqual({"status": "SAFE", "reason": "valid"}, result)
        self.assertEqual(2, fake_client.completions.calls)
        self.assertEqual(1, len(log["errors"]))

    def test_standard_prompt_is_truncated_to_token_budget(self):
        engine = AIEngine()
        with (
            patch.object(config, "AI_CONTEXT_WINDOW", 600),
            patch.object(config, "AI_MAX_TOKENS", 100),
            patch.object(config, "AI_TOKEN_SAFETY_MARGIN", 50),
            patch.object(config, "MAIN_FILE_TOKEN_BUDGET", 200),
        ):
            messages, info = engine._standard_messages("large.py", "print('x')\n" * 5000)

        self.assertTrue(info["main_file_truncated"])
        self.assertLessEqual(info["estimated_input_tokens"], info["input_limit"])
        self.assertIn("TRUNCATED TO TOKEN BUDGET", messages[1]["content"])

    def test_deep_prompt_respects_shared_dependency_budget(self):
        engine = AIEngine()
        dependencies = {f"pkg/dep_{index}.py": "value = 'x'\n" * 1000 for index in range(10)}
        with (
            patch.object(config, "AI_CONTEXT_WINDOW", 1400),
            patch.object(config, "AI_MAX_TOKENS", 150),
            patch.object(config, "AI_TOKEN_SAFETY_MARGIN", 50),
            patch.object(config, "MAIN_FILE_TOKEN_BUDGET", 300),
            patch.object(config, "DEPENDENCY_TOKEN_BUDGET", 600),
            patch.object(config, "DEPENDENCY_FILE_TOKEN_BUDGET", 180),
        ):
            _, info = engine._deep_messages("main.py", "print('main')\n" * 1000, dependencies)

        self.assertLessEqual(info["estimated_input_tokens"], info["input_limit"])
        self.assertLessEqual(info["dependency_tokens_used"], 600)
        self.assertLess(info["dependencies_included"], len(dependencies))


if __name__ == "__main__":
    unittest.main()
