"""Anthropic Claude API 客户端"""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.domain.models.base import BaseLLMClient, ModelConfig


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude 客户端实现"""

    def __init__(self, config: ModelConfig, client=None, async_client=None):
        super().__init__(config)
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "x-api-key": config.api_key.get_secret_value(),
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        self.client = client or httpx.Client(timeout=60.0)
        self.async_client = async_client or httpx.AsyncClient(timeout=60.0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = [{"role": "user", "content": prompt}]
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "system": system_prompt or "",
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = self.client.post(self.api_url, headers=self.headers, json=payload)
        response.raise_for_status()
        result = response.json()
        content = result["content"][0]
        return content.get("text", content.get("value", ""))

    async def achat(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = [{"role": "user", "content": prompt}]
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "system": system_prompt or "",
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = await self.async_client.post(self.api_url, headers=self.headers, json=payload)
        response.raise_for_status()
        result = response.json()
        content = result["content"][0]
        return content.get("text", content.get("value", ""))
