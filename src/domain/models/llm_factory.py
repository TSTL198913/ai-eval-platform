from typing import Optional

from src.domain.models.base import BaseLLMClient, ModelConfig, default_model_config
from src.domain.models.deepseek import DeepSeekClient
from src.domain.models.stub import StubLLMClient


def create_llm_client(client: Optional[BaseLLMClient] = None) -> BaseLLMClient:
    """创建 LLM 客户端。测试可注入 mock；生产从环境变量读取配置。"""
    if client is not None:
        return client

    config = default_model_config()
    api_key = config.api_key.get_secret_value()
    if not api_key or api_key == "stub-no-key":
        return StubLLMClient(ModelConfig(api_key="stub", model_name="stub-model"))

    return DeepSeekClient(config)
