"""OpenAI API 客户端"""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.domain.models.base import BaseLLMClient, ModelConfig


class OpenAIClient(BaseLLMClient):
    """OpenAI 客户端实现"""

    def __init__(self, config: ModelConfig, client=None, async_client=None):
        super().__init__(config)
        self.api_url = config.base_url or "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        self.client = client or httpx.Client(timeout=30.0)
        self.async_client = async_client or httpx.AsyncClient(timeout=30.0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = self._build_messages(prompt, system_prompt)
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = self.client.post(self.api_url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def achat(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = self._build_messages(prompt, system_prompt)
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = await self.async_client.post(self.api_url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
