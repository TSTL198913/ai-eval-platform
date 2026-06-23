"""
LLM Factory 单元测试
测试目标：验证模型客户端创建、配置加载、缓存管理等核心功能
"""

import threading
from unittest.mock import MagicMock

import pytest

from src.domain.models.base import ModelConfig, default_model_config
from src.domain.models.llm_factory import (
    ModelProvider,
    ModelRegistry,
    _env_config_cache,
    _llm_client_cache,
    create_llm_client,
    load_config,
)


class TestModelProvider:
    """模型提供者枚举测试"""

    def test_provider_values(self):
        """验证提供者枚举值"""
        assert ModelProvider.DEEPSEEK == "deepseek"
        assert ModelProvider.OPENAI == "openai"
        assert ModelProvider.ANTHROPIC == "anthropic"
        assert ModelProvider.OLLAMA == "ollama"
        assert ModelProvider.QWEN == "qwen"


class TestModelRegistry:
    """模型注册中心测试"""

    def test_register_and_get_client_class(self):
        """注册并获取客户端类"""

        class TestClient:
            pass

        ModelRegistry.register("test_provider")(TestClient)
        assert ModelRegistry.get_client_class("test_provider") == TestClient

    def test_register_case_insensitive(self):
        """注册大小写不敏感"""

        class TestClient:
            pass

        ModelRegistry.register("TEST_PROVIDER")(TestClient)
        assert ModelRegistry.get_client_class("test_provider") == TestClient
        assert ModelRegistry.get_client_class("TEST_PROVIDER") == TestClient

    def test_get_nonexistent_provider(self):
        """获取不存在的提供者应返回None"""
        assert ModelRegistry.get_client_class("nonexistent") is None

    def test_list_providers_returns_list(self):
        """列出所有提供者应返回列表"""
        providers = ModelRegistry.list_providers()
        assert isinstance(providers, list)
        assert "deepseek" in providers


class TestLoadConfig:
    """配置加载测试"""

    def test_load_default_config(self):
        """加载默认配置"""
        config = load_config()
        assert isinstance(config, ModelConfig)
        assert config.model_name is not None

    def test_load_deepseek_config(self):
        """加载DeepSeek配置"""
        _env_config_cache.clear()
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("DEEPSEEK_API_KEY", "test-key")
            mp.setenv("DEEPSEEK_MODEL", "test-model")
            mp.setenv("DEEPSEEK_BASE_URL", "http://test.com")
            config = load_config("deepseek", use_cache=False)
            assert config.api_key.get_secret_value() == "test-key"
            assert config.model_name == "test-model"
            assert config.base_url == "http://test.com"
        _env_config_cache.clear()

    def test_load_openai_config(self):
        """加载OpenAI配置"""
        _env_config_cache.clear()
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("OPENAI_API_KEY", "openai-key")
            mp.setenv("OPENAI_MODEL", "gpt-4")
            config = load_config("openai", use_cache=False)
            assert config.api_key.get_secret_value() == "openai-key"
            assert config.model_name == "gpt-4"
        _env_config_cache.clear()

    def test_load_config_with_env_cache(self):
        """配置加载应使用环境变量缓存"""
        _env_config_cache.clear()
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("DEEPSEEK_API_KEY", "cached-key")
            config1 = load_config("deepseek")
            config2 = load_config("deepseek")
            assert config1 is config2
        _env_config_cache.clear()

    def test_load_config_bypasses_cache(self):
        """绕过缓存重新加载"""
        _env_config_cache.clear()
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("DEEPSEEK_API_KEY", "key1")
            load_config("deepseek")
            mp.setenv("DEEPSEEK_API_KEY", "key2")
            config2 = load_config("deepseek", use_cache=False)
            assert config2.api_key.get_secret_value() == "key2"
        _env_config_cache.clear()


class TestDefaultModelConfig:
    """默认模型配置测试"""

    def test_default_config_returns_model_config(self):
        """默认配置应返回ModelConfig"""
        config = default_model_config()
        assert isinstance(config, ModelConfig)
        assert config.model_name == "deepseek-chat"


class TestCreateLLMClient:
    """创建LLM客户端测试"""

    def test_create_client_default_provider(self):
        """创建默认提供者客户端"""
        client = create_llm_client()
        assert client is not None

    def test_create_client_specific_provider(self):
        """创建指定提供者客户端"""
        client = create_llm_client(provider="deepseek")
        assert client is not None

    def test_create_client_caching(self):
        """客户端应被缓存"""
        _llm_client_cache.clear()
        client1 = create_llm_client(provider="deepseek")
        client2 = create_llm_client(provider="deepseek")
        assert client1 is client2
        _llm_client_cache.clear()

    def test_create_client_different_providers_not_cached(self):
        """不同提供者不应共享缓存"""
        _llm_client_cache.clear()
        client1 = create_llm_client(provider="deepseek")
        client2 = create_llm_client(provider="openai")
        assert client1 is not client2
        _llm_client_cache.clear()

    def test_create_client_concurrent_safety(self):
        """并发创建客户端应安全"""
        clients = []

        def create_client():
            clients.append(create_llm_client())

        threads = [threading.Thread(target=create_client) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(clients) == 10
        assert all(c is not None for c in clients)

    def test_create_client_with_custom_config(self):
        """使用自定义配置创建客户端"""
        config = ModelConfig(api_key="custom-key", model_name="custom-model")
        client = create_llm_client(provider="deepseek", config=config)
        assert client is not None


class TestCacheManagement:
    """缓存管理测试"""

    def test_client_cache_is_dict(self):
        """客户端缓存应为字典类型"""
        assert isinstance(_llm_client_cache, dict)

    def test_env_config_cache_is_dict(self):
        """环境配置缓存应为字典类型"""
        assert isinstance(_env_config_cache, dict)

    def test_cache_clear(self):
        """缓存可被清空"""
        _llm_client_cache["test"] = MagicMock()
        assert "test" in _llm_client_cache
        _llm_client_cache.clear()
        assert "test" not in _llm_client_cache
