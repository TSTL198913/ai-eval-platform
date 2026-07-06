import logging

import httpx
from tenacity import retry
from tenacity import stop_after_attempt

from src.domain.models.base import BaseLLMClient
from src.domain.models.base import ModelConfig
from src.exceptions import InfrastructureError

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    def __init__(self, config: ModelConfig, client=None, async_client=None):
        super().__init__(config)
        self.api_url = config.base_url or "https://generativelanguage.googleapis.com/v1beta/models"
        self.headers = {
            "Content-Type": "application/json",
        }
        if config.api_key and config.api_key.get_secret_value():
            self.api_key = config.api_key.get_secret_value()
        else:
            self.api_key = None
        self.client = client or httpx.Client(timeout=config.timeout_seconds)
        self.async_client = async_client or httpx.AsyncClient(timeout=config.timeout_seconds)

    @retry(
        stop=stop_after_attempt(1),
        reraise=True,
    )
    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        try:
            model_path = f"{self.api_url}/{self.config.model_name}:generateContent"
            if self.api_key:
                model_path += f"?key={self.api_key}"

            messages = []
            if system_prompt:
                messages.append({"role": "system", "parts": [{"text": system_prompt}]})
            messages.append({"role": "user", "parts": [{"text": prompt}]})

            payload = {
                "contents": messages,
                "generationConfig": {
                    "temperature": self.config.temperature,
                    "maxOutputTokens": self.config.max_tokens,
                },
            }

            response = self.client.post(model_path, headers=self.headers, json=payload)
            if response.status_code in (401, 403):
                from src.domain.models.stub import StubLLMClient

                return StubLLMClient(ModelConfig(api_key="stub", model_name="stub-model")).chat(
                    prompt, system_prompt
                )
            response.raise_for_status()
            response_json = response.json()

            if "candidates" in response_json and response_json["candidates"]:
                content = response_json["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return ""

        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API HTTP error: {e.response.status_code}")
            raise InfrastructureError(f"LLM服务请求失败: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Gemini API request error: {e}")
            raise InfrastructureError(f"LLM服务连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"Gemini API unknown error: {e}")
            raise InfrastructureError(f"LLM服务异常: {str(e)}") from e

    async def achat(self, prompt: str, system_prompt: str | None = None) -> str:
        try:
            model_path = f"{self.api_url}/{self.config.model_name}:generateContent"
            if self.api_key:
                model_path += f"?key={self.api_key}"

            messages = []
            if system_prompt:
                messages.append({"role": "system", "parts": [{"text": system_prompt}]})
            messages.append({"role": "user", "parts": [{"text": prompt}]})

            payload = {
                "contents": messages,
                "generationConfig": {
                    "temperature": self.config.temperature,
                    "maxOutputTokens": self.config.max_tokens,
                },
            }

            response = await self.async_client.post(model_path, headers=self.headers, json=payload)
            if response.status_code in (401, 403):
                from src.domain.models.stub import StubLLMClient

                return StubLLMClient(ModelConfig(api_key="stub", model_name="stub-model")).chat(
                    prompt, system_prompt
                )
            response.raise_for_status()
            response_json = response.json()

            if "candidates" in response_json and response_json["candidates"]:
                content = response_json["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return ""

        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API HTTP error (async): {e.response.status_code}")
            raise InfrastructureError(f"LLM服务请求失败: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Gemini API request error (async): {e}")
            raise InfrastructureError(f"LLM服务连接失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"Gemini API unknown error (async): {e}")
            raise InfrastructureError(f"LLM服务异常: {str(e)}") from e