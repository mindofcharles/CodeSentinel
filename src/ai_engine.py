import logging
from openai import OpenAI, APIConnectionError
from .config import config

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

    def analyze_code(self, filename: str, content: str) -> str:
        """
        Sends code to the LLM for security analysis.
        Returns the analysis result.
        """
        if not self.client:
            return "ERROR: AI Client not initialized (Missing API Key?)"

        system_prompt = (
            "You are CodeSentinel, an expert Cyber Security Auditor. "
            "Your task is to analyze the provided source code for: "
            "1. Malicious intent (backdoors, data exfiltration, logic bombs). "
            "2. Dangerous coding practices (SQL injection, eval(), hardcoded secrets). "
            "3. Obfuscation techniques used to hide payload. "
            "\n"
            "Output Format:"
            "- If the code appears BENIGN/SAFE, simply reply with '[SAFE]' and a very brief reason."
            "- If the code is SUSPICIOUS or MALICIOUS, reply with '[DANGER]' or '[WARNING]' followed by a concise explanation of the specific threat."
            "- Keep your response under 3 sentences."
        )

        user_prompt = f"File Name: {filename}\n\nCode Content:\n```\n{content}\n```"

        try:
            response = self.client.chat.completions.create(
                model=config.AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=config.AI_TEMPERATURE, 
                max_tokens=config.AI_MAX_TOKENS
            )
            return response.choices[0].message.content.strip()
        except APIConnectionError:
            return "ERROR: Could not connect to AI Provider. Check URL/Network."
        except Exception as e:
            return f"ERROR: AI Analysis failed - {str(e)}"

    def analyze_deep(self, filename: str, content: str, dependencies: dict, full_context: bool = False) -> str:
        """
        Performs deep analysis of a file with the context of its dependencies.
        `dependencies` is a dict: {filename: content}
        """
        if not self.client:
            return "ERROR: AI Client not initialized"

        context_type = "Full Source Code" if full_context else "Skeletal Structure (classes/functions)"
        
        system_prompt = (
            "You are CodeSentinel, performing a DEEP SECURITY AUDIT. "
            f"You are provided with the 'Main File' code and the '{context_type}' of its dependencies. "
            "Your goal is to trace logic and data flow to identify cross-file vulnerabilities or malicious intent. "
            "\n"
            "Output Format:"
            "- Reply with '[SAFE]' if the system logic is benign."
            "- Reply with '[DANGER]' or '[WARNING]' if you find cross-file threats, explaining the chain of execution."
            "- Keep your response under 4 sentences."
        )

        context_str = ""
        for dep_name, dep_content in dependencies.items():
            context_str += f"--- Dependency ({'FULL' if full_context else 'Skeleton'}): {dep_name} ---\n{dep_content}\n\n"

        user_prompt = (
            f"MAIN FILE: {filename}\n"
            f"CODE:\n```\n{content}\n```\n\n"
            f"DEPENDENCY CONTEXT:\n{context_str}"
        )

        try:
            response = self.client.chat.completions.create(
                model=config.AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=config.AI_TEMPERATURE,
                max_tokens=config.AI_MAX_TOKENS
            )
            result = response.choices[0].message.content.strip()
            return result if result else "ERROR: AI returned an empty response."
        except Exception as e:
            return f"ERROR: Deep Analysis failed - {str(e)}"
