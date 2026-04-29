import unittest

from src.ai_engine import AIEngine


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


class TestAIEngine(unittest.TestCase):
    def test_context_limit_error_does_not_retry(self):
        engine = AIEngine()
        fake_client = _FakeClient()
        engine.client = fake_client

        result, _ = engine._get_json_response([{"role": "user", "content": "x"}])

        self.assertEqual("ERROR", result["status"])
        self.assertIn("context limit", result["reason"].lower())
        self.assertEqual(1, fake_client.completions.calls)


if __name__ == "__main__":
    unittest.main()
