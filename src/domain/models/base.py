import os
from abc import ABC, abstractmethod

from pydantic import BaseModel, SecretStr


class ModelConfig(BaseModel):
    """模型配置：参数集中管理，API Key 从环境变量读取。"""

    api_key: SecretStr
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 1024
    base_url: str | None = None
    timeout_seconds: float = 30.0


def default_model_config() -> ModelConfig:
    api_key = os.getenv("DEEPSEEK_API_KEY", "stub-no-key")
    model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    return ModelConfig(api_key=api_key, model_name=model_name)


class BaseLLMClient(ABC):
    def __init__(self, config: ModelConfig):
        self.config = config

    def _build_messages(self, prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": system_prompt or "You are a helpful assistant.",
            },
            {"role": "user", "content": prompt},
        ]

    def _build_payload(self, prompt: str, system_prompt: str | None = None) -> dict:
        return {
            "model": self.config.model_name,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

    @abstractmethod
    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        pass

    @abstractmethod
    async def achat(self, prompt: str, system_prompt: str | None = None) -> str:
        pass
