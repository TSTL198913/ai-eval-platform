"""
配置模块测试用例
"""

import os
from unittest.mock import patch

import pytest

from src.config import Settings, get_settings


class TestSettingsDefaults:
    """测试配置默认值"""

    def test_default_app_name(self):
        """测试默认应用名称"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.app_name == "ai-eval-platform"

    def test_default_app_version(self):
        """测试默认版本号"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.app_version == "1.0.0"

    def test_default_debug_disabled(self):
        """测试默认调试模式禁用"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.debug is False

    def test_default_database_url(self):
        """测试默认数据库连接"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.database_url == "sqlite:///./eval_platform.db"

    def test_default_redis_url(self):
        """测试默认 Redis 连接"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.redis_url == "redis://localhost:6379/0"

    def test_default_rabbitmq_url(self):
        """测试默认 RabbitMQ 连接"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
            assert settings.rabbitmq_url == "amqp://guest:guest@localhost:5672/"

    def test_default_llm_provider(self):
        """测试默认 LLM Provider"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.default_llm_provider == "stub"

    def test_default_rate_limit(self):
        """测试默认限流配置"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.rate_limit_requests == 100
            assert settings.rate_limit_burst == 150

    def test_default_circuit_breaker(self):
        """测试默认熔断器配置"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.circuit_breaker_failure_threshold == 5
            assert settings.circuit_breaker_timeout_seconds == 60


class TestSettingsEnvironmentOverride:
    """测试环境变量覆盖"""

    def test_database_url_from_env(self):
        """测试数据库 URL 从环境变量覆盖"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/test"}):
            settings = Settings()
            assert settings.database_url == "postgresql://user:pass@localhost:5432/test"

    def test_redis_url_from_env(self):
        """测试 Redis URL 从环境变量覆盖"""
        with patch.dict(os.environ, {"REDIS_URL": "redis://redis:6379/1"}):
            settings = Settings()
            assert settings.redis_url == "redis://redis:6379/1"

    def test_debug_from_env(self):
        """测试调试模式从环境变量覆盖"""
        with patch.dict(os.environ, {"DEBUG": "true"}):
            settings = Settings()
            assert settings.debug is True

    def test_llm_api_keys_from_env(self):
        """测试 LLM API Key 从环境变量覆盖"""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test-deepseek-key",
                "OPENAI_API_KEY": "test-openai-key",
            },
        ):
            settings = Settings()
            assert settings.deepseek_api_key == "test-deepseek-key"
            assert settings.openai_api_key == "test-openai-key"

    def test_case_insensitive_env_vars(self):
        """测试环境变量不区分大小写"""
        with patch.dict(os.environ, {"database_url": "sqlite:///./test.db"}):
            settings = Settings()
            assert settings.database_url == "sqlite:///./test.db"


class TestGetSettingsSingleton:
    """测试 get_settings 单例机制"""

    def test_singleton_returns_same_instance(self):
        """测试单例返回相同实例"""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_lru_cache_used(self):
        """测试使用 LRU 缓存"""
        # 清除缓存
        get_settings.cache_clear()

        # 第一次调用
        settings1 = get_settings()
        # 第二次调用应该返回相同实例
        settings2 = get_settings()

        assert settings1 is settings2

    def test_cache_clear_returns_new_instance(self):
        """测试清除缓存后返回新实例"""
        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        assert settings1 is not settings2


class TestSettingsValidation:
    """测试配置验证"""

    def test_extra_env_vars_ignored(self):
        """测试额外环境变量被忽略"""
        with patch.dict(os.environ, {"UNKNOWN_VAR": "test-value"}):
            # 应该不会抛出异常
            settings = Settings()
            assert settings is not None

    def test_timeout_configs(self):
        """测试超时配置"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.evaluation_timeout == 30
            assert settings.max_concurrent_evaluations == 10

    def test_otel_config(self):
        """测试 OpenTelemetry 配置"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.otel_enabled is False
            assert settings.otel_service_name == "ai-eval-platform"
            assert settings.otel_exporter_endpoint is None

    def test_prometheus_config(self):
        """测试 Prometheus 配置"""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            assert settings.prometheus_enabled is True