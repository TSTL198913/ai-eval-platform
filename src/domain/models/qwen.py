"""阿里云通义千问 API 客户端"""

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.domain.models.base import BaseLLMClient, ModelConfig
from src.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


class QwenClient(BaseLLMClient):
    """阿里云通义千问客户端"""

    def __init__(self, config: ModelConfig, client=None, async_client=None):
        super().__init__(config)
        self.api_url = (
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        )
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
        try:
            messages = self._build_messages(prompt, system_prompt)
            payload = {
                "model": self.config.model_name,
                "input": {"messages": messages},
                "parameters": {
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
            }
            response = self.client.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return result["output"]["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(f"Qwen API HTTP error: {e.response.status_code}")
            raise InfrastructureError(f"LLM服务请求失败: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Qwen API request error: {e}")
            raise InfrastructureError(f"LLM服务连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"Qwen API unknown error: {e}")
            raise InfrastructureError(f"LLM服务异常: {str(e)}") from e

    async def achat(self, prompt: str, system_prompt: str | None = None) -> str:
        try:
            messages = self._build_messages(prompt, system_prompt)
            payload = {
                "model": self.config.model_name,
                "input": {"messages": messages},
                "parameters": {
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
            }
            response = await self.async_client.post(
                self.api_url, headers=self.headers, json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result["output"]["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(f"Qwen API HTTP error (async): {e.response.status_code}")
            raise InfrastructureError(f"LLM服务请求失败: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Qwen API request error (async): {e}")
            raise InfrastructureError(f"LLM服务连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"Qwen API unknown error (async): {e}")
            raise InfrastructureError(f"LLM服务异常: {str(e)}") from e
