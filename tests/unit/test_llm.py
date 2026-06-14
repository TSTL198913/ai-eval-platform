"""
LLM 客户端单元测试
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.llm.base import (
    LLMConfig,
    LLMProvider,
    OpenAIClient,
    DeepSeekClient,
    AnthropicClient,
    OllamaClient,
    StubLLMClient,
    LLMClientFactory,
    create_llm_client,
    ChatResponse,
)


class TestLLMConfig:
    """LLM 配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = LLMConfig()
        
        assert config.provider == LLMProvider.DEEPSEEK
        assert config.temperature == 0.7
        assert config.max_tokens == 1024
        assert config.timeout == 30.0
        assert config.retry_times == 3

    def test_custom_config(self):
        """测试自定义配置"""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="sk-test",
            model_name="gpt-4",
            temperature=0.5,
            max_tokens=2000,
        )
        
        assert config.provider == LLMProvider.OPENAI
        assert config.api_key == "sk-test"
        assert config.model_name == "gpt-4"
        assert config.temperature == 0.5
        assert config.max_tokens == 2000


class TestStubLLMClient:
    """桩客户端测试"""

    def test_stub_client_response(self):
        """测试桩客户端返回"""
        client = StubLLMClient()
        
        assert client.provider == LLMProvider.STUB
        
        # 异步调用 (chat 是 async 方法)
        import asyncio
        response = asyncio.run(client.chat("Hello", "You are a helpful assistant"))
        
        assert isinstance(response, ChatResponse)
        assert "Hello" in response.content or "模拟" in response.content
        assert response.model == "stub-model"

    def test_stub_client_async(self):
        """测试桩客户端异步调用"""
        import asyncio
        client = StubLLMClient()
        
        response = asyncio.run(client.achat("Hello"))
        
        assert isinstance(response, ChatResponse)
        assert len(response.content) > 0


class TestOpenAIClient:
    """OpenAI 客户端测试"""

    def test_openai_client_creation(self):
        """测试 OpenAI 客户端创建"""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="sk-test",
            model_name="gpt-4",
        )
        
        client = OpenAIClient(config)
        
        assert client.provider == LLMProvider.OPENAI
        assert client.config.model_name == "gpt-4"

    def test_build_messages(self):
        """测试消息构建"""
        config = LLMConfig(provider=LLMProvider.OPENAI)
        client = OpenAIClient(config)
        
        messages = client._build_messages("Hello", "You are helpful")
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_build_messages_no_system(self):
        """测试无系统提示的消息构建"""
        config = LLMConfig(provider=LLMProvider.OPENAI)
        client = OpenAIClient(config)
        
        messages = client._build_messages("Hello", None)
        
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    def test_parse_response(self):
        """测试响应解析"""
        config = LLMConfig(provider=LLMProvider.OPENAI)
        client = OpenAIClient(config)
        
        raw = {
            "choices": [{"message": {"content": "Test response"}}],
            "model": "gpt-4",
            "usage": {"total_tokens": 100},
        }
        
        response = client._parse_response(raw)
        
        assert response.content == "Test response"
        assert response.model == "gpt-4"
        assert response.usage["total_tokens"] == 100


class TestDeepSeekClient:
    """DeepSeek 客户端测试"""

    def test_deepseek_client_default_url(self):
        """测试 DeepSeek 默认 URL"""
        config = LLMConfig(provider=LLMProvider.DEEPSEEK)
        client = DeepSeekClient(config)
        
        assert "deepseek.com" in client.config.base_url


class TestLLMClientFactory:
    """LLM 客户端工厂测试"""

    def test_create_openai_client(self):
        """测试创建 OpenAI 客户端"""
        config = LLMConfig(provider=LLMProvider.OPENAI)
        client = LLMClientFactory.create(config)
        
        assert isinstance(client, OpenAIClient)

    def test_create_deepseek_client(self):
        """测试创建 DeepSeek 客户端"""
        config = LLMConfig(provider=LLMProvider.DEEPSEEK)
        client = LLMClientFactory.create(config)
        
        assert isinstance(client, DeepSeekClient)

    def test_create_stub_client(self):
        """测试创建桩客户端"""
        config = LLMConfig(provider=LLMProvider.STUB)
        client = LLMClientFactory.create(config)
        
        assert isinstance(client, StubLLMClient)

    def test_unsupported_provider(self):
        """测试不支持的提供者"""
        config = LLMConfig(provider="unknown_provider")
        
        with pytest.raises(ValueError):
            LLMClientFactory.create(config)


class TestCreateLLMClient:
    """create_llm_client 函数测试"""

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"})
    def test_create_from_env(self):
        """测试从环境变量创建"""
        client = create_llm_client(provider="deepseek")
        
        assert client.config.api_key == "test-key"

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": ""})
    def test_create_stub_without_key(self):
        """测试无 API key 时创建桩客户端"""
        client = create_llm_client(api_key="")
        
        # Empty key should create StubLLMClient
        assert isinstance(client, StubLLMClient)

    def test_create_with_model_name(self):
        """测试指定模型名称"""
        client = create_llm_client(
            provider="openai",
            api_key="test",
            model_name="gpt-4-turbo",
        )
        
        assert client.config.model_name == "gpt-4-turbo"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
