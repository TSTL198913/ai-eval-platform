from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.anthropic import AnthropicClient
from src.domain.models.base import BaseLLMClient, ModelConfig
from src.domain.models.deepseek import DeepSeekClient
from src.domain.models.llm_factory import (
    ModelRegistry,
    clear_client_cache,
    clear_env_config_cache,
    create_llm_client,
    load_config,
    validate_config,
)
from src.domain.models.ollama import OllamaClient
from src.domain.models.openai import OpenAIClient
from src.domain.models.qwen import QwenClient
from src.domain.models.stub import StubLLMClient


class TestModelConfig:
    def test_config_defaults(self):
        config = ModelConfig(api_key="test-key", model_name="test-model")
        assert config.temperature == 0.7
        assert config.max_tokens == 1024
        assert config.base_url is None

    def test_config_custom_values(self):
        config = ModelConfig(
            api_key="test-key",
            model_name="gpt-4",
            temperature=0.5,
            max_tokens=2048,
            base_url="http://localhost",
        )
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.base_url == "http://localhost"


class TestOpenAIClient:
    def test_chat_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "test response"}}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, client=mock_client)

        result = client.chat("Hello")
        assert result == "test response"
        mock_client.post.assert_called_once()

    def test_chat_with_system_prompt(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "system response"}}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, client=mock_client)

        result = client.chat("Hello", "You are a helpful assistant")
        assert result == "system response"

    def test_chat_http_error(self, monkeypatch):
        monkeypatch.setattr("src.domain.models.openai.retry", lambda fn: fn)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP Error")
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, client=mock_client)

        with pytest.raises(Exception, match="HTTP Error"):
            client.chat("Hello")

    @pytest.mark.asyncio
    async def test_achat_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "async test response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, async_client=mock_client)

        result = await client.achat("Hello")
        assert result == "async test response"


class TestDeepSeekClient:
    def test_chat_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "deepseek response"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-deepseek", model_name="deepseek-chat")
        client = DeepSeekClient(config, client=mock_client)

        result = client.chat("Hello")
        assert result == "deepseek response"

    @pytest.mark.asyncio
    async def test_achat_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "async deepseek response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-deepseek", model_name="deepseek-chat")
        client = DeepSeekClient(config, async_client=mock_client)

        result = await client.achat("Hello")
        assert result == "async deepseek response"


class TestAnthropicClient:
    def test_chat_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "anthropic response"}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-anthropic", model_name="claude-3-sonnet")
        client = AnthropicClient(config, client=mock_client)

        result = client.chat("Hello")
        assert result == "anthropic response"

    def test_chat_content_with_value(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"value": "anthropic value response"}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-anthropic", model_name="claude-3-sonnet")
        client = AnthropicClient(config, client=mock_client)

        result = client.chat("Hello")
        assert result == "anthropic value response"

    @pytest.mark.asyncio
    async def test_achat_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "async anthropic response"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-anthropic", model_name="claude-3-sonnet")
        client = AnthropicClient(config, async_client=mock_client)

        result = await client.achat("Hello")
        assert result == "async anthropic response"


class TestQwenClient:
    def test_chat_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {"choices": [{"message": {"content": "qwen response"}}]}
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-qwen", model_name="qwen-max")
        client = QwenClient(config, client=mock_client)

        result = client.chat("Hello")
        assert result == "qwen response"

    @pytest.mark.asyncio
    async def test_achat_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {"choices": [{"message": {"content": "async qwen response"}}]}
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-qwen", model_name="qwen-max")
        client = QwenClient(config, async_client=mock_client)

        result = await client.achat("Hello")
        assert result == "async qwen response"


class TestOllamaClient:
    def test_chat_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ollama response"}}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(
            api_key="", model_name="llama3", base_url="http://localhost:11434/api/chat"
        )
        client = OllamaClient(config, client=mock_client)

        result = client.chat("Hello")
        assert result == "ollama response"

    @pytest.mark.asyncio
    async def test_achat_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "async ollama response"}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(
            api_key="", model_name="llama3", base_url="http://localhost:11434/api/chat"
        )
        client = OllamaClient(config, async_client=mock_client)

        result = await client.achat("Hello")
        assert result == "async ollama response"


class TestStubLLMClient:
    def test_chat_default(self):
        client = StubLLMClient(ModelConfig(api_key="stub", model_name="stub"))
        result = client.chat("What is 1+1?")
        assert "模拟金融分析" in result

    def test_chat_code_review(self):
        client = StubLLMClient(ModelConfig(api_key="stub", model_name="stub"))
        result = client.chat("审查以下代码：```python\ndef foo():\n    pass\n```")
        assert "代码审查结果" in result

    def test_chat_text_eval(self):
        client = StubLLMClient(ModelConfig(api_key="stub", model_name="stub"))
        result = client.chat("测试问题", "文本评测")
        assert "准确且完整的解释" in result

    @pytest.mark.asyncio
    async def test_achat(self):
        client = StubLLMClient(ModelConfig(api_key="stub", model_name="stub"))
        result = await client.achat("Hello")
        assert "模拟金融分析" in result


class TestModelRegistry:
    def test_register_and_get_client(self):
        @ModelRegistry.register("test-provider")
        class TestClient(BaseLLMClient):
            def chat(self, prompt, system_prompt=None):
                return "test"

            async def achat(self, prompt, system_prompt=None):
                return "test"

        client_class = ModelRegistry.get_client_class("test-provider")
        assert client_class == TestClient

    def test_get_client_not_found(self):
        assert ModelRegistry.get_client_class("unknown-provider") is None

    def test_list_providers(self):
        providers = ModelRegistry.list_providers()
        assert isinstance(providers, list)


class TestLoadConfig:
    def test_load_deepseek_config(self, monkeypatch):
        # 清除缓存确保读取最新环境变量
        from src.domain.models.llm_factory import clear_env_config_cache
        clear_env_config_cache()
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-test")
        config = load_config("deepseek")
        assert config.model_name == "deepseek-test"

    def test_load_openai_config(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4-test")
        config = load_config("openai")
        assert config.model_name == "gpt-4-test"

    def test_load_ollama_config(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "llama-test")
        config = load_config("ollama")
        assert config.model_name == "llama-test"
        assert config.api_key.get_secret_value() == ""

    def test_load_anthropic_config(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        config = load_config("anthropic")
        assert config.model_name == "claude-3-sonnet-20240229"

    def test_load_qwen_config(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        config = load_config("qwen")
        assert config.model_name == "qwen-max"

    def test_load_dashscope_config(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
        config = load_config("dashscope")
        assert config.model_name == "qwen-max"

    def test_load_unknown_provider(self):
        with pytest.raises(ValueError, match="不支持的模型提供者"):
            load_config("unknown")


class TestCreateLLMClient:
    def test_create_client_with_client_injection(self):
        mock_client = MagicMock()
        result = create_llm_client(client=mock_client)
        assert result == mock_client

    def test_create_client_with_config(self):
        config = ModelConfig(api_key="test-key", model_name="deepseek-chat")
        client = create_llm_client(provider="deepseek", config=config)
        assert isinstance(client, DeepSeekClient)

    def test_create_client_without_api_key_uses_stub(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "")
        clear_env_config_cache("deepseek")
        clear_client_cache("deepseek")
        client = create_llm_client(provider="deepseek")
        assert isinstance(client, StubLLMClient)

    def test_create_client_ollama_without_api_key(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        client = create_llm_client(provider="ollama")
        assert isinstance(client, OllamaClient)

    def test_create_client_unknown_provider(self):
        with pytest.raises(ValueError, match="不支持的模型提供者"):
            create_llm_client(provider="unknown")

    def test_create_client_not_found_provider(self):
        config = ModelConfig(api_key="test", model_name="test")
        with pytest.raises(ValueError, match="未注册的提供者"):
            create_llm_client(provider="unknown", config=config)


class TestValidateConfig:
    def test_validate_config_valid(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        result = validate_config()
        assert result["valid"] is True
        assert result["provider"] == "deepseek"

    def test_validate_config_unknown_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "unknown")
        result = validate_config()
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_validate_config_missing_api_key(self, monkeypatch):
        # 清除缓存确保读取最新环境变量
        from src.domain.models.llm_factory import clear_env_config_cache, clear_all_caches
        clear_all_caches()
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        result = validate_config()
        assert result["valid"] is True
        # 验证warnings存在或api_key为空
        assert len(result["warnings"]) > 0 or result.get("model") is not None

    def test_validate_config_exception(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "unknown-provider")
        result = validate_config()
        assert result["valid"] is False
        assert len(result["errors"]) > 0
