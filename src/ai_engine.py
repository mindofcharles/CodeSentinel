import logging
import json
from openai import APIConnectionError, APIStatusError, BadRequestError, OpenAI
from .config_parser import config

class AIEngine:
    def __init__(self):
        self.client = None
        self.setup_client()

    def setup_client(self):
        """Initializes the OpenAI client with configuration."""
        if config.OPENAI_API_KEY:
            self.client = OpenAI(
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_BASE_URL
            )
        else:
            logging.warning("OPENAI_API_KEY not found. AI features will be disabled or fail.")

    def check_connectivity(self) -> bool:
        """Checks if the AI provider is reachable and the model is available."""
        if not self.client:
            return False
        try:
            # Simple list models call to check connectivity
            self.client.models.list()
            return True
        except Exception as e:
            logging.error(f"API Connectivity check failed: {e}")
            return False

    def _get_json_response(self, messages: list) -> tuple[dict, dict]:
        """Helper to get a JSON response from the LLM, handling potential Markdown wrapping."""
        interaction_log = {
            "request_messages": messages,
            "raw_response": ""
        }
        
        last_error_reason = "Unknown Error"
        
        def is_context_limit_error(error: Exception) -> bool:
            message = str(error).lower()
            context_markers = [
                "context length",
                "context window",
                "maximum context",
                "max context",
                "token limit",
                "too many tokens",
                "reduce the length",
                "prompt is too long",
            ]
            return any(marker in message for marker in context_markers)

        for attempt in range(config.AI_MAX_RETRIES):
            content = ""
            try:
                response = self.client.chat.completions.create(
                    model=config.AI_MODEL,
                    messages=messages,
                    temperature=config.AI_TEMPERATURE,
                    max_tokens=config.AI_MAX_TOKENS,
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                if not content:
                    content = ""
                content = content.strip()
                interaction_log["raw_response"] = content
                
                if not content:
                    logging.warning(f"AI returned empty output on attempt {attempt + 1}. Retrying...")
                    last_error_reason = "AI returned empty output."
                    continue
                
                # Robust JSON extraction: handle Markdown blocks
                clean_content = content
                if clean_content.startswith("```"):
                    # Remove starting marker (e.g., ```json or ```)
                    clean_content = clean_content.split("\n", 1)[-1]
                    # Remove ending marker
                    if clean_content.endswith("```"):
                        clean_content = clean_content.rsplit("```", 1)[0]
                    clean_content = clean_content.strip()
                
                # If the first split didn't catch everything (e.g. text before/after blocks)
                # we can try a regex-like approach to find the first '{' and last '}'
                start_idx = clean_content.find('{')
                end_idx = clean_content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    clean_content = clean_content[start_idx:end_idx+1]
                    
                # If AI returned an empty JSON object due to some issue
                if clean_content == "{}":
                    logging.warning(f"AI returned empty JSON on attempt {attempt + 1}. Retrying...")
                    last_error_reason = "AI returned empty JSON."
                    continue
    
                return json.loads(clean_content), interaction_log
                
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse AI JSON. Raw content: \n{content}\nError: {e}")
                # Do a fallback check just in case the AI didn't use JSON format at all but returned text
                if "[DANGER]" in content.upper() or "DANGER" in content.upper():
                    return {"status": "DANGER", "reason": content[:200]}, interaction_log
                elif "[WARNING]" in content.upper() or "WARNING" in content.upper():
                    return {"status": "WARNING", "reason": content[:200]}, interaction_log
                elif "[SAFE]" in content.upper() or "SAFE" in content.upper():
                    return {"status": "SAFE", "reason": content[:200]}, interaction_log
                
                logging.warning(f"Invalid JSON and fallback failed on attempt {attempt + 1}. Retrying...")
                last_error_reason = "AI returned invalid JSON. Check interaction logs."
                continue
            except BadRequestError as e:
                if is_context_limit_error(e):
                    return {"status": "ERROR", "reason": f"AI context limit exceeded: {str(e)}"}, interaction_log
                logging.error(f"AI bad request on attempt {attempt + 1}: {e}")
                last_error_reason = f"AI bad request: {str(e)}"
                continue
            except APIStatusError as e:
                if getattr(e, "status_code", None) == 400 and is_context_limit_error(e):
                    return {"status": "ERROR", "reason": f"AI context limit exceeded: {str(e)}"}, interaction_log
                logging.error(f"AI API status error on attempt {attempt + 1}: {e}")
                last_error_reason = f"AI API status error: {str(e)}"
                continue
            except APIConnectionError:
                return {"status": "ERROR", "reason": "Could not connect to AI Provider."}, interaction_log
            except Exception as e:
                if is_context_limit_error(e):
                    return {"status": "ERROR", "reason": f"AI context limit exceeded: {str(e)}"}, interaction_log
                logging.error(f"AI Analysis failed on attempt {attempt + 1}: {e}")
                last_error_reason = f"AI Analysis failed: {str(e)}"
                continue

        return {"status": "ERROR", "reason": f"Failed after {config.AI_MAX_RETRIES} attempts. Last error: {last_error_reason}"}, interaction_log

    def analyze_code(self, filename: str, content: str) -> tuple[dict, dict]:
        """Sends code to the LLM for security analysis."""
        if not self.client:
            return {"status": "ERROR", "reason": "AI Client not initialized."}, {}

        prompt_conf = config.PROMPTS.get("standard", {})
        sys_prompt = prompt_conf.get("system", "Analyze code for security.")
        user_tmpl = prompt_conf.get("user", "File: {filename}\nCode: {content}")
        
        user_prompt = user_tmpl.format(filename=filename, content=content)

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return self._get_json_response(messages)

    def analyze_deep(self, filename: str, content: str, dependencies: dict, full_context: bool = False) -> tuple[dict, dict]:
        """Performs deep analysis of a file with dependency context."""
        if not self.client:
            return {"status": "ERROR", "reason": "AI Client not initialized."}, {}

        prompt_conf = config.PROMPTS.get("deep", {})
        sys_prompt = prompt_conf.get("system", "Perform deep security audit.")
        user_tmpl = prompt_conf.get("user", "File: {filename}\nCode: {content}\nContext: {context}")

        context_str = ""
        for dep_name, dep_content in dependencies.items():
            context_str += f"--- Dependency: {dep_name} ---\n{dep_content}\n\n"

        user_prompt = user_tmpl.format(filename=filename, content=content, context=context_str)

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return self._get_json_response(messages)
