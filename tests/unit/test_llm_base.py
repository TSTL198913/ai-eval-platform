"""测试 llm/base.py - LLM 客户端抽象基类"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.llm.base import (
    AnthropicClient,
    BaseLLMClient,
    ChatResponse,
    DeepSeekClient,
    LLMClientFactory,
    LLMConfig,
    LLMProvider,
    OllamaClient,
    OpenAIClient,
    StubLLMClient,
)


class TestChatResponse:
    """测试响应模型"""

    def test_creation(self):
        resp = ChatResponse(
            content="Hello world",
            model="gpt-4",
            usage={"total_tokens": 10},
            latency_ms=100.0,
        )
        assert resp.content == "Hello world"
        assert resp.model == "gpt-4"
        assert resp.usage["total_tokens"] == 10
        assert resp.latency_ms == 100.0


class TestStubLLMClient:
    """测试 Stub 客户端"""

    async def test_do_request(self):
        client = StubLLMClient()
        result = await client._do_request([{"role": "user", "content": "Hello"}])
        assert "模拟响应" in result["content"]
        assert result["model"] == "stub-model"

    async def test_chat(self):
        client = StubLLMClient()
        resp = await client.chat("Hello")
        assert isinstance(resp, ChatResponse)
        assert "模拟响应" in resp.content

    async def test_achat(self):
        client = StubLLMClient()
        resp = await client.achat("Hello")
        assert isinstance(resp, ChatResponse)

    def test_parse_response(self):
        client = StubLLMClient()
        raw = {
            "content": "Hello",
            "model": "gpt-4",
            "usage": {"total_tokens": 10},
        }
        resp = client._parse_response(raw)
        assert resp.content == "Hello"
        assert resp.model == "stub-model"
        assert resp.usage["total_tokens"] == 10

    def test_parse_response_default(self):
        client = StubLLMClient()
        raw = {}
        resp = client._parse_response(raw)
        assert resp.content == "Stub response"

    def test_provider(self):
        client = StubLLMClient()
        assert client.provider == LLMProvider.STUB

    def test_build_messages(self):
        client = StubLLMClient()
        messages = client._build_messages("Hello", None)
        assert messages == [{"role": "user", "content": "Hello"}]


class TestOpenAIClient:
    """测试 OpenAI 客户端"""

    def test_initialization(self):
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name="gpt-4",
            api_key="sk-test",
        )
        client = OpenAIClient(config)
        assert client.config.model_name == "gpt-4"
        assert client.config.base_url == "https://api.openai.com/v1"

    def test_provider(self):
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="sk-test",
        )
        client = OpenAIClient(config)
        assert client.provider == LLMProvider.OPENAI

    def test_build_messages(self):
        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="sk-test")
        client = OpenAIClient(config)
        messages = client._build_messages("Hello", "You are helpful")
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_build_messages_no_system(self):
        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="sk-test")
        client = OpenAIClient(config)
        messages = client._build_messages("Hello", None)
        assert len(messages) == 1

    def test_parse_response(self):
        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="sk-test")
        client = OpenAIClient(config)
        raw = {
            "choices": [{"message": {"content": "Hello"}}],
            "model": "gpt-4",
            "usage": {"total_tokens": 5},
        }
        resp = client._parse_response(raw)
        assert resp.content == "Hello"
        assert resp.model == "gpt-4"

    async def test_do_request(self):
        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="sk-test", model_name="gpt-4")
        client = OpenAIClient(config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello"}}],
            "model": "gpt-4",
            "usage": {"total_tokens": 5},
        }
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client._do_request([{"role": "user", "content": "Hi"}])
            assert result["choices"][0]["message"]["content"] == "Hello"


class TestAnthropicClient:
    """测试 Anthropic 客户端"""

    def test_initialization(self):
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model_name="claude-3",
            api_key="sk-ant-test",
        )
        client = AnthropicClient(config)
        assert client.config.model_name == "claude-3"

    def test_provider(self):
        config = LLMConfig(provider=LLMProvider.ANTHROPIC, api_key="sk-ant-test")
        client = AnthropicClient(config)
        assert client.provider == LLMProvider.ANTHROPIC

    def test_parse_response(self):
        config = LLMConfig(provider=LLMProvider.ANTHROPIC, api_key="sk-ant-test")
        client = AnthropicClient(config)
        raw = {
            "content": [{"text": "Hello from Claude"}],
            "model": "claude-3",
            "usage": {"input_tokens": 5, "output_tokens": 10},
        }
        resp = client._parse_response(raw)
        assert "Claude" in resp.content
        assert resp.model == "claude-3"


class TestOllamaClient:
    """测试 Ollama 客户端"""

    def test_initialization(self):
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model_name="llama2",
            base_url="http://localhost:11434",
        )
        client = OllamaClient(config)
        assert client.config.base_url == "http://localhost:11434"
        assert client.config.model_name == "llama2"

    def test_provider(self):
        config = LLMConfig(provider=LLMProvider.OLLAMA, base_url="http://localhost:11434")
        client = OllamaClient(config)
        assert client.provider == LLMProvider.OLLAMA

    def test_parse_response(self):
        config = LLMConfig(provider=LLMProvider.OLLAMA, base_url="http://localhost:11434")
        client = OllamaClient(config)
        raw = {
            "message": {"content": "Hello from Ollama"},
            "model": "llama2",
        }
        resp = client._parse_response(raw)
        assert "Ollama" in resp.content


class TestDeepSeekClient:
    """测试 DeepSeek 客户端"""

    def test_initialization(self):
        config = LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="sk-ds-test",
        )
        client = DeepSeekClient(config)
        assert client.config.model_name == "deepseek-chat"
        assert client.config.base_url == "https://api.deepseek.com/v1"

    def test_provider(self):
        config = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="sk-ds-test")
        client = DeepSeekClient(config)
        assert client.provider == LLMProvider.DEEPSEEK


class TestLLMClientFactory:
    """测试 LLM 客户端工厂"""

    def test_create_openai(self):
        config = LLMConfig(provider=LLMProvider.OPENAI, api_key="sk-test")
        client = LLMClientFactory.create(config)
        assert isinstance(client, OpenAIClient)

    def test_create_stub(self):
        config = LLMConfig(provider=LLMProvider.STUB)
        client = LLMClientFactory.create(config)
        assert isinstance(client, StubLLMClient)

    def test_create_unsupported(self):
        class FakeProvider:
            value = "fake"

        config = LLMConfig(provider=FakeProvider())
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMClientFactory.create(config)

    def test_register(self):
        class CustomClient(BaseLLMClient):
            @property
            def provider(self):
                return LLMProvider.STUB

            def _build_messages(self, prompt, system_prompt):
                return []

            def _parse_response(self, raw_response):
                return ChatResponse(content="", model="")

            async def _do_request(self, messages):
                return {}

        LLMClientFactory.register(LLMProvider.STUB, CustomClient)
        config = LLMConfig(provider=LLMProvider.STUB)
        client = LLMClientFactory.create(config)
        assert isinstance(client, CustomClient)


class TestBaseLLMClientAbstract:
    """测试抽象基类方法"""

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseLLMClient(LLMConfig(provider=LLMProvider.STUB))

    def test_subclass_must_implement(self):
        class BadClient(BaseLLMClient):
            pass

        with pytest.raises(TypeError):
            BadClient(LLMConfig(provider=LLMProvider.STUB))
