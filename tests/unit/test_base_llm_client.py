from unittest.mock import MagicMock

import pytest

from src.domain.models.base import BaseLLMClient, ModelConfig, default_model_config


class ConcreteLLMClient(BaseLLMClient):
    """具体实现用于测试"""

    def chat(self, prompt, system_prompt=None):
        return "test response"

    async def achat(self, prompt, system_prompt=None):
        return "async test response"


class TestModelConfig:
    """模型配置测试"""

    def test_config_with_secret_api_key(self):
        """测试密钥被隐藏"""
        config = ModelConfig(api_key="secret-key", model_name="test-model")
        assert "secret-key" not in str(config)
        assert config.api_key.get_secret_value() == "secret-key"

    def test_config_defaults(self):
        """测试默认值"""
        config = ModelConfig(api_key="key", model_name="model")
        assert config.temperature == 0.7
        assert config.max_tokens == 1024
        assert config.base_url is None

    def test_config_custom_values(self):
        """测试自定义值"""
        config = ModelConfig(
            api_key="key",
            model_name="model",
            temperature=0.5,
            max_tokens=2048,
            base_url="http://localhost",
        )
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.base_url == "http://localhost"


class TestDefaultModelConfig:
    """默认配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = default_model_config()
        assert isinstance(config, ModelConfig)
        assert config.model_name == "deepseek-chat"


class TestBaseLLMClient:
    """基础LLM客户端测试"""

    def setup_method(self):
        self.config = ModelConfig(api_key="test-key", model_name="test-model")
        self.client = ConcreteLLMClient(self.config)

    def test_init(self):
        """测试初始化"""
        assert self.client.config == self.config

    def test_build_messages_with_system_prompt(self):
        """测试构建消息带系统提示"""
        messages = self.client._build_messages("Hello", "You are helpful")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_build_messages_without_system_prompt(self):
        """测试构建消息无系统提示"""
        messages = self.client._build_messages("Hello", None)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."

    def test_build_payload(self):
        """测试构建payload"""
        payload = self.client._build_payload("Hello", "You are helpful")
        assert payload["model"] == "test-model"
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 1024
        assert len(payload["messages"]) == 2

    def test_chat(self):
        """测试chat方法"""
        result = self.client.chat("Hello")
        assert result == "test response"

    def test_achat(self):
        """测试achat方法"""
        import asyncio

        result = asyncio.run(self.client.achat("Hello"))
        assert result == "async test response"