"""Ollama 本地模型客户端"""

import httpx
import logging

from src.domain.models.base import BaseLLMClient, ModelConfig
from src.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient):
    """Ollama 本地模型客户端"""

    def __init__(self, config: ModelConfig, client=None, async_client=None):
        super().__init__(config)
        self.api_url = config.base_url or "http://localhost:11434/api/chat"
        self.client = client or httpx.Client(timeout=120.0)
        self.async_client = async_client or httpx.AsyncClient(timeout=120.0)

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        try:
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
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API HTTP error: {e.response.status_code}")
            raise InfrastructureError(f"LLM服务请求失败: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Ollama API request error: {e}")
            raise InfrastructureError(f"LLM服务连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"Ollama API unknown error: {e}")
            raise InfrastructureError(f"LLM服务异常: {str(e)}") from e

    async def achat(self, prompt: str, system_prompt: str | None = None) -> str:
        try:
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
            return response.json()["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API HTTP error (async): {e.response.status_code}")
            raise InfrastructureError(f"LLM服务请求失败: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Ollama API request error (async): {e}")
            raise InfrastructureError(f"LLM服务连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"Ollama API unknown error (async): {e}")
            raise InfrastructureError(f"LLM服务异常: {str(e)}") from e