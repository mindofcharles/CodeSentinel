# API Integration Guide

CodeSentinel uses the OpenAI Python SDK, making it compatible with any API that adheres to the OpenAI chat completions specification.

## Local LLMs (Recommended)

Running a local LLM ensures your code never leaves your machine.

### LM Studio

1. Load a model (e.g., `Meta-Llama-3-8B-Instruct`).
2. Go to the **Local Server** tab and click **Start Server**.
3. In `config.yaml`, set:

   ```yaml
   openai_base_url: "http://localhost:1234/v1"
   ai_model: "your-model-id" # Copy from LM Studio
   ```

### llama.cpp

1. Start a simple service using `llama-server`, with the following recommended parameters:

   ```bash
   llama-server -m ~/model.gguf -c 32768 -np 1 --port 1234
   ```

2. In `config.yaml`, set:

   ```yaml
   openai_base_url: "http://localhost:1234/v1"
   ai_model: "your-model-id" # Copy from llama.cpp
   ```

   Actually, for the llama-server service started in the manner described above, you can enter any model name you want.

   However, you cannot leave it blank, as the system will prevent it from running with an empty model name.

## Cloud Providers

### OpenAI

1. Get an API key from the [OpenAI Dashboard](https://platform.openai.com/).
2. Set your environment variable: `export OPENAI_API_KEY="sk-..."`.
3. In `config.yaml`, set:

   ```yaml
   openai_base_url: "https://api.openai.com/v1"
   ai_model: "gpt-4o"
   ```

### Others (Groq, Together AI, etc.)

Simply update the `openai_base_url` and `ai_model` in `config.yaml` to match the provider's documentation.
