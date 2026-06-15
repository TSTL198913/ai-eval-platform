"""Ollama 本地模型客户端"""

import httpx

from src.domain.models.base import BaseLLMClient, ModelConfig


class OllamaClient(BaseLLMClient):
    """Ollama 本地模型客户端"""

    def __init__(self, config: ModelConfig, client=None, async_client=None):
        super().__init__(config)
        self.api_url = config.base_url or "http://localhost:11434/api/chat"
        self.client = client or httpx.Client(timeout=120.0)
        self.async_client = async_client or httpx.AsyncClient(timeout=120.0)

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = self._build_messages(prompt, system_prompt)
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            },
        }
        response = self.client.post(self.api_url, json=payload)
        response.raise_for_status()
        return response.json()["message"]["content"]

    async def achat(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = self._build_messages(prompt, system_prompt)
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            },
        }
        response = await self.async_client.post(self.api_url, json=payload)
        response.raise_for_status()
        return
