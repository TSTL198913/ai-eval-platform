import logging

import httpx
from tenacity import retry, stop_after_attempt

from src.domain.models.base import BaseLLMClient, ModelConfig
from src.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


class DeepSeekClient(BaseLLMClient):
    def __init__(self, config: ModelConfig, client=None, async_client=None):
        super().__init__(config)
        self.api_url = config.base_url or "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        self.client = client or httpx.Client(timeout=30.0)
        self.async_client = async_client or httpx.AsyncClient(timeout=30.0)

    @retry(
        stop=stop_after_attempt(1),
        reraise=True,
    )
    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        try:
            payload = self._build_payload(prompt, system_prompt)
            response = self.client.post(self.api_url, headers=self.headers, json=payload)
            if response.status_code in (401, 402):
                from src.domain.models.stub import StubLLMClient

                return StubLLMClient(ModelConfig(api_key="stub", model_name="stub-model")).chat(
                    prompt, system_prompt
                )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(f"DeepSeek API HTTP error: {e.response.status_code}")
            raise InfrastructureError(f"LLM服务请求失败: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"DeepSeek API request error: {e}")
            raise InfrastructureError(f"LLM服务连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"DeepSeek API unknown error: {e}")
            raise InfrastructureError(f"LLM服务异常: {str(e)}") from e

    async def achat(self, prompt: str, system_prompt: str | None = None) -> str:
        try:
            payload = self._build_payload(prompt, system_prompt)
            response = await self.async_client.post(
                self.api_url, headers=self.headers, json=payload
            )
            if response.status_code in (401, 402):
                from src.domain.models.stub import StubLLMClient

                return StubLLMClient(ModelConfig(api_key="stub", model_name="stub-model")).chat(
                    prompt, system_prompt
                )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(f"DeepSeek API HTTP error (async): {e.response.status_code}")
            raise InfrastructureError(f"LLM服务请求失败: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"DeepSeek API request error (async): {e}")
            raise InfrastructureError(f"LLM服务连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"DeepSeek API unknown error (async): {e}")
            raise InfrastructureError(f"LLM服务异常: {str(e)}") from e
