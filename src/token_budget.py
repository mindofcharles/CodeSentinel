import math
import pathlib

from tokenizers import Tokenizer
from tokenizers.pre_tokenizers import ByteLevel


TRUNCATION_MARKER = "\n...[TRUNCATED TO TOKEN BUDGET]..."


class TokenBudgetError(ValueError):
    """Raised when configured prompt limits cannot fit required prompt text."""


class TokenCounter:
    """Counts model tokens with tokenizer.json or a conservative local fallback."""

    def __init__(self, tokenizer_path: str = ""):
        self.tokenizer = None
        self.byte_level = ByteLevel(add_prefix_space=False)
        if tokenizer_path:
            path = pathlib.Path(tokenizer_path)
            if not path.is_file():
                raise TokenBudgetError(f"Tokenizer file '{path}' not found.")
            try:
                self.tokenizer = Tokenizer.from_file(str(path))
            except Exception as exc:
                raise TokenBudgetError(f"Failed to load tokenizer '{path}': {exc}") from exc

    @property
    def mode(self) -> str:
        return "tokenizer.json" if self.tokenizer else "bytelevel-estimate"

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self.tokenizer:
            return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

        # ByteLevel provides model-like lexical splitting. UTF-8 bytes / 3 is
        # intentionally conservative for source code and CJK without a model tokenizer.
        pieces = len(self.byte_level.pre_tokenize_str(text))
        byte_estimate = math.ceil(len(text.encode("utf-8")) / 3)
        return max(pieces, byte_estimate, 1)

    def truncate(self, text: str, max_tokens: int, marker: str = TRUNCATION_MARKER) -> tuple[str, bool]:
        if max_tokens <= 0:
            return "", bool(text)
        if self.count(text) <= max_tokens:
            return text, False

        marker_tokens = self.count(marker)
        if marker_tokens >= max_tokens:
            return self._truncate_without_marker(marker, max_tokens), True

        content_budget = max_tokens - marker_tokens
        low, high = 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if self.count(text[:middle]) <= content_budget:
                low = middle
            else:
                high = middle - 1
        return text[:low] + marker, True

    def _truncate_without_marker(self, text: str, max_tokens: int) -> str:
        low, high = 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if self.count(text[:middle]) <= max_tokens:
                low = middle
            else:
                high = middle - 1
        return text[:low]
