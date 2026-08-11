import json
import logging
from typing import Any

from openai import APIConnectionError, APIStatusError, BadRequestError, OpenAI

from .config_parser import config
from .token_budget import TokenBudgetError, TokenCounter


VALID_STATUSES = {"SAFE", "WARNING", "DANGER"}


class AIEngine:
    def __init__(self):
        self.client = None
        self.token_counter = TokenCounter(config.TOKENIZER_PATH)
        self.setup_client()

    def setup_client(self):
        if config.OPENAI_API_KEY:
            self.client = OpenAI(
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_BASE_URL,
            )
        else:
            logging.warning("OPENAI_API_KEY not found. AI features are disabled.")

    def check_connectivity(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.models.list()
            return True
        except Exception as exc:
            logging.error("API connectivity check failed: %s", exc)
            return False

    @staticmethod
    def _error_payload(error: Exception) -> Any:
        body = getattr(error, "body", None)
        if body is not None:
            return body
        response = getattr(error, "response", None)
        if response is not None:
            try:
                return response.json()
            except Exception:
                pass
        return None

    @classmethod
    def _is_context_limit_error(cls, error: Exception) -> bool:
        payload = cls._error_payload(error)
        payload_text = json.dumps(payload, ensure_ascii=False).lower() if payload is not None else ""
        message = f"{error} {payload_text}".lower()
        structured_codes = {
            "context_length_exceeded",
            "exceed_context_size_error",
            "context_window_exceeded",
            "too_many_tokens",
        }

        def contains_code(value):
            if isinstance(value, dict):
                if str(value.get("code", "")).lower() in structured_codes:
                    return True
                if str(value.get("type", "")).lower() in structured_codes:
                    return True
                return any(contains_code(item) for item in value.values())
            if isinstance(value, list):
                return any(contains_code(item) for item in value)
            return False

        context_markers = [
            "context length",
            "context window",
            "context size",
            "maximum context",
            "max context",
            "token limit",
            "too many tokens",
            "reduce the length",
            "prompt is too long",
            "exceeds the available context",
        ]
        return contains_code(payload) or any(marker in message for marker in context_markers)

    @staticmethod
    def _clean_json_content(content: str) -> str:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end >= start:
            cleaned = cleaned[start : end + 1]
        return cleaned

    @staticmethod
    def _validate_result(value: Any) -> dict:
        if not isinstance(value, dict):
            raise ValueError("AI response must be a JSON object.")
        status = value.get("status")
        reason = value.get("reason")
        if not isinstance(status, str) or status.upper() not in VALID_STATUSES:
            raise ValueError("AI response status must be SAFE, WARNING, or DANGER.")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("AI response reason must be a non-empty string.")
        if len(reason) > 4000:
            raise ValueError("AI response reason exceeds the 4000-character limit.")
        return {"status": status.upper(), "reason": reason.strip()}

    def _get_json_response(self, messages: list, budget_info: dict = None) -> tuple[dict, dict]:
        interaction_log = {
            "request_messages": messages,
            "raw_response": "",
            "token_budget": budget_info or {},
            "errors": [],
        }
        last_error_reason = "Unknown error"

        for attempt in range(config.AI_MAX_RETRIES):
            content = ""
            try:
                response = self.client.chat.completions.create(
                    model=config.AI_MODEL,
                    messages=messages,
                    temperature=config.AI_TEMPERATURE,
                    max_tokens=config.AI_MAX_TOKENS,
                    response_format={"type": "json_object"},
                )
                content = (response.choices[0].message.content or "").strip()
                interaction_log["raw_response"] = content
                if not content:
                    raise ValueError("AI returned empty output.")

                cleaned = self._clean_json_content(content)
                if cleaned == "{}":
                    raise ValueError("AI returned an empty JSON object.")
                return self._validate_result(json.loads(cleaned)), interaction_log
            except (json.JSONDecodeError, ValueError) as exc:
                last_error_reason = f"Invalid AI response: {exc}"
                interaction_log["errors"].append(last_error_reason)
                logging.warning("%s Attempt %d/%d.", last_error_reason, attempt + 1, config.AI_MAX_RETRIES)
            except BadRequestError as exc:
                if self._is_context_limit_error(exc):
                    reason = f"AI context limit exceeded: {exc}"
                    interaction_log["errors"].append(reason)
                    return {"status": "ERROR", "reason": reason}, interaction_log
                last_error_reason = f"AI bad request: {exc}"
                interaction_log["errors"].append(last_error_reason)
            except APIStatusError as exc:
                if self._is_context_limit_error(exc):
                    reason = f"AI context limit exceeded: {exc}"
                    interaction_log["errors"].append(reason)
                    return {"status": "ERROR", "reason": reason}, interaction_log
                last_error_reason = f"AI API status error: {exc}"
                interaction_log["errors"].append(last_error_reason)
            except APIConnectionError as exc:
                reason = f"Could not connect to AI provider: {exc}"
                interaction_log["errors"].append(reason)
                return {"status": "ERROR", "reason": reason}, interaction_log
            except Exception as exc:
                if self._is_context_limit_error(exc):
                    reason = f"AI context limit exceeded: {exc}"
                    interaction_log["errors"].append(reason)
                    return {"status": "ERROR", "reason": reason}, interaction_log
                last_error_reason = f"AI analysis failed: {exc}"
                interaction_log["errors"].append(last_error_reason)
                logging.exception("AI analysis attempt %d failed", attempt + 1)

        return {
            "status": "ERROR",
            "reason": f"Failed after {config.AI_MAX_RETRIES} attempts. Last error: {last_error_reason}",
        }, interaction_log

    def _message_tokens(self, messages: list) -> int:
        # The fixed overhead is intentionally conservative across chat templates.
        return 2 + sum(4 + self.token_counter.count(str(message.get("content", ""))) for message in messages)

    def _input_token_limit(self) -> int:
        limit = config.AI_CONTEXT_WINDOW - config.AI_MAX_TOKENS - config.AI_TOKEN_SAFETY_MARGIN
        if limit <= 0:
            raise TokenBudgetError("Configured context window leaves no room for input tokens.")
        return limit

    def _standard_messages(self, filename: str, content: str):
        prompt_config = config.PROMPTS.get("standard", {})
        system_prompt = prompt_config.get("system", "Analyze code for security.")
        user_template = prompt_config.get("user", "File: {filename}\nCode: {content}")
        empty_user = user_template.format(filename=filename, content="")
        base_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": empty_user},
        ]
        input_limit = self._input_token_limit()
        available = input_limit - self._message_tokens(base_messages)
        if available <= 0:
            raise TokenBudgetError("System and user prompt templates exceed the input token budget.")

        content_budget = min(config.MAIN_FILE_TOKEN_BUDGET, available)
        fitted_content, truncated = self.token_counter.truncate(content, content_budget)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_template.format(filename=filename, content=fitted_content)},
        ]
        return messages, {
            "tokenizer_mode": self.token_counter.mode,
            "input_limit": input_limit,
            "estimated_input_tokens": self._message_tokens(messages),
            "main_file_original_tokens": self.token_counter.count(content),
            "main_file_sent_tokens": self.token_counter.count(fitted_content),
            "main_file_truncated": truncated,
            "dependencies_included": 0,
        }

    def _deep_messages(self, filename: str, content: str, dependencies: dict):
        prompt_config = config.PROMPTS.get("deep", {})
        system_prompt = prompt_config.get("system", "Perform deep security audit.")
        user_template = prompt_config.get(
            "user", "File: {filename}\nCode: {content}\nContext: {context}"
        )
        input_limit = self._input_token_limit()
        empty_user = user_template.format(filename=filename, content="", context="")
        base_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": empty_user},
        ]
        available = input_limit - self._message_tokens(base_messages)
        if available <= 0:
            raise TokenBudgetError("Deep prompt templates exceed the input token budget.")

        main_budget = min(config.MAIN_FILE_TOKEN_BUDGET, available)
        fitted_content, main_truncated = self.token_counter.truncate(content, main_budget)
        context_parts = []
        dependencies_truncated = []
        dependency_tokens_used = 0

        for dependency_name, dependency_content in dependencies.items():
            header = f"--- Dependency: {dependency_name} ---\n"
            footer = "\n\n"
            wrapper_tokens = self.token_counter.count(header + footer)
            remaining_dependency_budget = config.DEPENDENCY_TOKEN_BUDGET - dependency_tokens_used
            if remaining_dependency_budget <= wrapper_tokens:
                break

            current_context = "".join(context_parts)
            messages_without_dependency = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_template.format(
                        filename=filename,
                        content=fitted_content,
                        context=current_context,
                    ),
                },
            ]
            prompt_remaining = input_limit - self._message_tokens(messages_without_dependency)
            allowed = min(
                config.DEPENDENCY_FILE_TOKEN_BUDGET,
                remaining_dependency_budget - wrapper_tokens,
                prompt_remaining - wrapper_tokens,
            )
            if allowed <= 0:
                break
            fitted_dependency, was_truncated = self.token_counter.truncate(dependency_content, allowed)
            part = header + fitted_dependency + footer
            part_tokens = self.token_counter.count(part)
            context_parts.append(part)
            dependency_tokens_used += part_tokens
            if was_truncated:
                dependencies_truncated.append(dependency_name)

        context = "".join(context_parts)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_template.format(
                    filename=filename,
                    content=fitted_content,
                    context=context,
                ),
            },
        ]
        estimated_tokens = self._message_tokens(messages)
        if estimated_tokens > input_limit:
            raise TokenBudgetError(
                f"Internal prompt budgeting error: estimated {estimated_tokens} tokens for a {input_limit}-token input limit."
            )

        return messages, {
            "tokenizer_mode": self.token_counter.mode,
            "input_limit": input_limit,
            "estimated_input_tokens": estimated_tokens,
            "main_file_original_tokens": self.token_counter.count(content),
            "main_file_sent_tokens": self.token_counter.count(fitted_content),
            "main_file_truncated": main_truncated,
            "dependencies_discovered": len(dependencies),
            "dependencies_included": len(context_parts),
            "dependency_tokens_used": dependency_tokens_used,
            "dependencies_truncated": dependencies_truncated,
        }

    def analyze_code(self, filename: str, content: str) -> tuple[dict, dict]:
        if not self.client:
            return {"status": "ERROR", "reason": "AI client not initialized."}, {}
        try:
            messages, budget_info = self._standard_messages(filename, content)
        except TokenBudgetError as exc:
            return {"status": "ERROR", "reason": f"Token budget error: {exc}"}, {}
        return self._get_json_response(messages, budget_info)

    def analyze_deep(
        self,
        filename: str,
        content: str,
        dependencies: dict,
    ) -> tuple[dict, dict]:
        if not self.client:
            return {"status": "ERROR", "reason": "AI client not initialized."}, {}
        try:
            messages, budget_info = self._deep_messages(filename, content, dependencies)
        except TokenBudgetError as exc:
            return {"status": "ERROR", "reason": f"Token budget error: {exc}"}, {}
        return self._get_json_response(messages, budget_info)
