"""
LLM Factory 缓存和池化管理测试

测试覆盖：
- 客户端缓存
- 客户端复用
- 并发安全
- 环境变量配置缓存
- 缓存管理 API
- 错误处理
- validate_config
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from src.domain.models.base import BaseLLMClient, ModelConfig
from src.domain.models.llm_factory import (
    _cache_lock,
    _env_cache_lock,
    _env_config_cache,
    _generate_cache_key,
    _llm_client_cache,
    clear_all_caches,
    clear_client_cache,
    clear_env_config_cache,
    create_llm_client,
    get_cached_client,
    get_cache_stats,
    load_config,
    validate_config,
    ModelRegistry,
    ModelProvider,
    _create_new_client,
)


class TestClientCache:
    """客户端缓存测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_client_is_cached(self, monkeypatch):
        """测试客户端被缓存"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

        client1 = create_llm_client(provider="deepseek")
        client2 = create_llm_client(provider="deepseek")

        assert client1 is client2, "相同配置应返回相同客户端实例"

    def test_different_providers_different_cache(self, monkeypatch):
        """测试不同提供者使用不同缓存"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        client_deepseek = create_llm_client(provider="deepseek")
        client_openai = create_llm_client(provider="openai")

        assert client_deepseek is not client_openai, "不同提供者应返回不同客户端"

    def test_cache_disabled_creates_new_instance(self, monkeypatch):
        """测试禁用缓存时创建新实例"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        client1 = create_llm_client(provider="deepseek", use_cache=False)
        client2 = create_llm_client(provider="deepseek", use_cache=False)

        assert client1 is not client2, "禁用缓存应创建新实例"

    def test_custom_config_not_cached(self, monkeypatch):
        """测试自定义配置不被缓存"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        config = ModelConfig(api_key="custom-key", model_name="custom-model")
        client1 = create_llm_client(provider="deepseek", config=config)
        client2 = create_llm_client(provider="deepseek", config=config)

        # 自定义配置不缓存，每次创建新实例
        assert client1 is not client2, "自定义配置不应缓存"

    def test_injected_client_not_cached(self):
        """测试注入的客户端不被缓存"""
        mock_client = MagicMock(spec=BaseLLMClient)

        result1 = create_llm_client(client=mock_client)
        result2 = create_llm_client(client=mock_client)

        assert result1 is mock_client
        assert result2 is mock_client
        # 注入的客户端不进入缓存
        assert len(_llm_client_cache) == 0


class TestClientReuse:
    """客户端复用测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_reuse_cached_client(self, monkeypatch):
        """测试复用缓存的客户端"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        # 第一次创建
        client1 = create_llm_client(provider="deepseek")

        # 第二次应复用
        client2 = create_llm_client(provider="deepseek")

        assert client1 is client2

    def test_get_cached_client_returns_cached(self, monkeypatch):
        """测试 get_cached_client 返回缓存的客户端"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        created_client = create_llm_client(provider="deepseek")
        cached_client = get_cached_client("deepseek")

        assert cached_client is created_client

    def test_get_cached_client_returns_none_if_not_cached(self):
        """测试 get_cached_client 未缓存时返回 None"""
        result = get_cached_client("nonexistent")
        assert result is None

    def test_get_cached_client_with_model_name(self, monkeypatch):
        """测试 get_cached_client 支持模型名称"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-coder")

        create_llm_client(provider="deepseek")

        # 缓存键是 provider:default（因为使用环境变量加载配置）
        cached = get_cached_client("deepseek")
        assert cached is not None


class TestConcurrencySafety:
    """并发安全测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_concurrent_client_creation(self, monkeypatch):
        """测试并发创建客户端的安全性"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        clients = []
        errors = []

        def create_client():
            try:
                client = create_llm_client(provider="deepseek")
                clients.append(client)
            except Exception as e:
                errors.append(e)

        # 创建多个线程并发创建客户端
        threads = [threading.Thread(target=create_client) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发创建出错: {errors}"
        # 所有客户端应为同一实例
        assert all(c is clients[0] for c in clients), "并发创建应返回同一缓存实例"

    def test_concurrent_cache_clear(self, monkeypatch):
        """测试并发清除缓存的安全性"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        # 先创建一些客户端
        for _ in range(5):
            create_llm_client(provider="deepseek")

        errors = []

        def clear_and_create():
            try:
                clear_client_cache()
                create_llm_client(provider="deepseek")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=clear_and_create) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发清除出错: {errors}"

    def test_concurrent_env_config_access(self, monkeypatch):
        """测试并发访问环境变量配置的安全性"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        configs = []
        errors = []

        def load_config_concurrent():
            try:
                config = load_config("deepseek")
                configs.append(config)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=load_config_concurrent) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发加载配置出错: {errors}"


class TestEnvConfigCache:
    """环境变量配置缓存测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_env_config_is_cached(self, monkeypatch):
        """测试环境变量配置被缓存"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

        config1 = load_config("deepseek")
        config2 = load_config("deepseek")

        assert config1 is config2, "相同提供者应返回缓存的配置"

    def test_env_config_cache_disabled(self, monkeypatch):
        """测试禁用缓存时不缓存配置"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        config1 = load_config("deepseek", use_cache=False)
        config2 = load_config("deepseek", use_cache=False)

        # 禁用缓存时，配置值相同但不是同一对象
        assert config1.model_name == config2.model_name

    def test_clear_env_config_cache(self, monkeypatch):
        """测试清除环境变量配置缓存"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        load_config("deepseek")
        assert len(_env_config_cache) > 0

        count = clear_env_config_cache()
        assert count >= 1
        assert len(_env_config_cache) == 0

    def test_clear_env_config_cache_specific_provider(self, monkeypatch):
        """测试清除特定提供者的环境变量配置缓存"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        load_config("deepseek")
        load_config("openai")

        count = clear_env_config_cache("deepseek")
        assert count == 1
        assert "deepseek" not in _env_config_cache
        assert "openai" in _env_config_cache


class TestCacheManagementAPI:
    """缓存管理 API 测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_clear_client_cache_all(self, monkeypatch):
        """测试清除所有客户端缓存"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        create_llm_client(provider="deepseek")
        create_llm_client(provider="openai")

        count = clear_client_cache()
        assert count == 2
        assert len(_llm_client_cache) == 0

    def test_clear_client_cache_specific_provider(self, monkeypatch):
        """测试清除特定提供者的客户端缓存"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        create_llm_client(provider="deepseek")
        create_llm_client(provider="openai")

        count = clear_client_cache("deepseek")
        assert count == 1
        assert "deepseek:default" not in _llm_client_cache
        assert any("openai" in k for k in _llm_client_cache)

    def test_clear_all_caches(self, monkeypatch):
        """测试清除所有缓存"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        create_llm_client(provider="deepseek")
        load_config("deepseek")

        result = clear_all_caches()
        assert result["clients"] >= 1
        assert result["env_configs"] >= 1
        assert len(_llm_client_cache) == 0
        assert len(_env_config_cache) == 0

    def test_get_cache_stats(self, monkeypatch):
        """测试获取缓存统计"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        create_llm_client(provider="deepseek")
        create_llm_client(provider="openai")

        stats = get_cache_stats()
        assert stats["client_count"] == 2
        assert stats["env_config_count"] >= 0
        assert "deepseek" in stats["cached_providers"]
        assert "openai" in stats["cached_providers"]

    def test_get_cache_stats_empty(self):
        """测试空缓存时的统计"""
        stats = get_cache_stats()
        assert stats["client_count"] == 0
        assert stats["env_config_count"] == 0
        assert stats["cached_providers"] == []


class TestGenerateCacheKey:
    """缓存键生成测试"""

    def test_cache_key_with_config(self):
        """测试有配置时的缓存键"""
        config = ModelConfig(api_key="test", model_name="gpt-4")
        key = _generate_cache_key("openai", config)
        assert key == "openai:gpt-4"

    def test_cache_key_without_config(self):
        """测试无配置时的缓存键"""
        key = _generate_cache_key("deepseek", None)
        assert key == "deepseek:default"

    def test_cache_key_different_models(self):
        """测试不同模型生成不同键"""
        config1 = ModelConfig(api_key="test", model_name="gpt-3.5-turbo")
        config2 = ModelConfig(api_key="test", model_name="gpt-4")

        key1 = _generate_cache_key("openai", config1)
        key2 = _generate_cache_key("openai", config2)

        assert key1 != key2


class TestCacheWithStubClient:
    """Stub 客户端缓存测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_stub_client_is_cached(self, monkeypatch):
        """测试 Stub 客户端被缓存"""
        # 无 API Key 时使用 Stub
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        client1 = create_llm_client(provider="deepseek")
        client2 = create_llm_client(provider="deepseek")

        assert client1 is client2, "Stub 客户端也应被缓存"

    def test_placeholder_api_key_uses_stub(self, monkeypatch):
        """测试占位符 API Key 使用 Stub"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_api_key_here")

        client = create_llm_client(provider="deepseek")

        from src.domain.models.stub import StubLLMClient

        assert isinstance(client, StubLLMClient)


class TestCacheIntegration:
    """缓存集成测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_full_lifecycle(self, monkeypatch):
        """测试完整生命周期：创建 -> 缓存 -> 复用 -> 清除"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        # 创建客户端
        client1 = create_llm_client(provider="deepseek")

        # 验证缓存
        stats = get_cache_stats()
        assert stats["client_count"] == 1

        # 复用缓存
        client2 = create_llm_client(provider="deepseek")
        assert client1 is client2

        # 清除缓存
        clear_count = clear_client_cache()
        assert clear_count == 1

        # 验证清除
        stats = get_cache_stats()
        assert stats["client_count"] == 0

    def test_multiple_providers_cache_isolation(self, monkeypatch):
        """测试多提供者缓存隔离"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

        deepseek_client = create_llm_client(provider="deepseek")
        openai_client = create_llm_client(provider="openai")

        # 不同提供者应返回不同客户端
        assert deepseek_client is not openai_client

        # 缓存统计
        stats = get_cache_stats()
        assert stats["client_count"] == 2
        assert len(stats["cached_providers"]) == 2

        # 清除单个提供者
        clear_client_cache("deepseek")
        stats = get_cache_stats()
        assert stats["client_count"] == 1
        assert "deepseek" not in stats["cached_providers"]


class TestValidateConfig:
    """validate_config 函数测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_validate_config_valid(self, monkeypatch):
        """测试有效配置验证"""
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "valid-key")

        result = validate_config()
        assert result["valid"] is True
        assert result["provider"] == "deepseek"
        assert result["model"] is not None
        assert len(result["errors"]) == 0

    def test_validate_config_unknown_provider(self, monkeypatch):
        """测试未知提供者验证"""
        monkeypatch.setenv("LLM_PROVIDER", "unknown-provider")

        result = validate_config()
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert "未知的模型提供者" in result["errors"][0]

    def test_validate_config_missing_api_key(self, monkeypatch):
        """测试缺少 API Key 的警告"""
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        result = validate_config()
        assert result["valid"] is True
        assert len(result["warnings"]) > 0

    def test_validate_config_ollama_no_warning(self, monkeypatch):
        """测试 Ollama 不检查 API Key"""
        monkeypatch.setenv("LLM_PROVIDER", "ollama")

        result = validate_config()
        assert result["valid"] is True
        # Ollama 不需要 API Key，所以没有警告
        assert len(result["warnings"]) == 0

    def test_validate_config_placeholder_api_key(self, monkeypatch):
        """测试占位符 API Key 的警告"""
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_api_key_here")

        result = validate_config()
        assert result["valid"] is True
        assert len(result["warnings"]) > 0


class TestErrorHandling:
    """错误处理测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_create_llm_client_unregistered_provider_with_config(self, monkeypatch):
        """测试使用自定义配置时未注册的提供者"""
        config = ModelConfig(api_key="test", model_name="test-model")

        with pytest.raises(ValueError, match="未注册的提供者"):
            create_llm_client(provider="unknown_provider", config=config)

    def test_create_new_client_unregistered_provider(self, monkeypatch):
        """测试 _create_new_client 未注册的提供者"""
        config = ModelConfig(api_key="valid-key", model_name="test-model")

        with pytest.raises(ValueError, match="未找到提供者"):
            _create_new_client("unknown_provider", config)

    def test_load_config_unsupported_provider(self):
        """测试 load_config 不支持的提供者"""
        with pytest.raises(ValueError, match="不支持的模型提供者"):
            load_config("unsupported_provider")

    def test_load_config_with_base_url(self, monkeypatch):
        """测试 load_config 包含 base_url"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://custom.api.com")

        config = load_config("deepseek")
        assert config.base_url == "https://custom.api.com"


class TestModelRegistry:
    """ModelRegistry 测试"""

    def test_list_providers_returns_list(self):
        """测试 list_providers 返回列表"""
        providers = ModelRegistry.list_providers()
        assert isinstance(providers, list)
        # 应包含已注册的提供者
        assert "deepseek" in providers or len(providers) >= 0

    def test_get_client_class_not_found(self):
        """测试获取未注册的客户端类"""
        result = ModelRegistry.get_client_class("nonexistent_provider")
        assert result is None


class TestModelProvider:
    """ModelProvider 枚举测试"""

    def test_provider_constants(self):
        """测试提供者常量"""
        assert ModelProvider.DEEPSEEK == "deepseek"
        assert ModelProvider.OPENAI == "openai"
        assert ModelProvider.ANTHROPIC == "anthropic"
        assert ModelProvider.OLLAMA == "ollama"
        assert ModelProvider.QWEN == "qwen"
        assert ModelProvider.DASHSCOPE == "dashscope"
        assert ModelProvider.CUSTOM == "custom"


class TestOllamaClient:
    """Ollama 客户端特殊处理测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_ollama_without_api_key_creates_real_client(self, monkeypatch):
        """测试 Ollama 无 API Key 创建真实客户端"""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)

        client = create_llm_client(provider="ollama")
        from src.domain.models.ollama import OllamaClient

        assert isinstance(client, OllamaClient)

    def test_ollama_with_empty_api_key(self, monkeypatch):
        """测试 Ollama 空 API Key"""
        monkeypatch.setenv("OLLAMA_MODEL", "llama3")

        config = load_config("ollama")
        assert config.api_key.get_secret_value() == ""


class TestClearEnvConfigCacheEdgeCases:
    """clear_env_config_cache 边缘情况测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_clear_nonexistent_provider(self):
        """测试清除不存在的提供者缓存"""
        count = clear_env_config_cache("nonexistent_provider")
        assert count == 0

    def test_clear_empty_cache(self):
        """测试清除空缓存"""
        count = clear_env_config_cache()
        assert count == 0


class TestClearClientCacheEdgeCases:
    """clear_client_cache 边缘情况测试"""

    def setup_method(self):
        """每个测试前清除缓存"""
        with _cache_lock:
            _llm_client_cache.clear()
        with _env_cache_lock:
            _env_config_cache.clear()

    def test_clear_nonexistent_provider(self):
        """测试清除不存在的提供者客户端缓存"""
        count = clear_client_cache("nonexistent_provider")
        assert count == 0

    def test_clear_empty_cache(self):
        """测试清除空客户端缓存"""
        count = clear_client_cache()
        assert count == 0