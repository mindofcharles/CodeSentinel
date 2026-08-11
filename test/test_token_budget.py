import unittest
import tempfile
from pathlib import Path

from tokenizers import Tokenizer, models, pre_tokenizers

from src.token_budget import TokenCounter


class TestTokenCounter(unittest.TestCase):
    def test_fallback_counts_and_truncates_unicode(self):
        counter = TokenCounter()
        content = "Security check print('hello')\n" * 100
        truncated, changed = counter.truncate(content, 40)

        self.assertTrue(changed)
        self.assertLessEqual(counter.count(truncated), 40)
        self.assertIn("TRUNCATED TO TOKEN BUDGET", truncated)

    def test_short_content_is_unchanged(self):
        counter = TokenCounter()
        content, changed = counter.truncate("hello", 100)
        self.assertEqual("hello", content)
        self.assertFalse(changed)

    def test_model_tokenizer_json_is_used_when_configured(self):
        tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0, "hello": 1, "world": 2}, unk_token="[UNK]"))
        tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
        with tempfile.TemporaryDirectory() as tmpdir:
            tokenizer_path = Path(tmpdir) / "tokenizer.json"
            tokenizer.save(str(tokenizer_path))
            counter = TokenCounter(str(tokenizer_path))

            self.assertEqual("tokenizer.json", counter.mode)
            self.assertEqual(2, counter.count("hello world"))
