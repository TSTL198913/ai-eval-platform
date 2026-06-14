"""
统一配置管理

使用 pydantic-settings 管理所有配置，支持：
1. 环境变量自动注入
2. 类型验证
3. 默认值设置
4. .env 文件加载
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用信息
    app_name: str = "ai-eval-platform"
    app_version: str = "1.0.0"
    debug: bool = False

    # 数据库
    database_url: str = Field(default="sqlite:///./eval_platform.db", description="数据库连接 URL")
    db_pool_size: int = Field(default=5, description="连接池大小")
    db_max_overflow: int = Field(default=10, description="最大溢出连接数")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis 连接 URL")
    redis_pool_size: int = Field(default=10, description="Redis 连接池大小")

    # RabbitMQ
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@localhost:5672/", description="RabbitMQ 连接 URL"
    )

    # Celery
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # LLM 配置
    deepseek_api_key: str | None = Field(default=None, description="DeepSeek API Key")
    openai_api_key: str | None = Field(default=None, description="OpenAI API Key")
    default_llm_provider: str = Field(default="stub", description="默认 LLM Provider")

    # 限流配置
    rate_limit_requests: int = Field(default=100, description="每秒请求数限制")
    rate_limit_burst: int = Field(default=150, description="突发限流大小")

    # 熔断器配置
    circuit_breaker_failure_threshold: int = Field(default=5, description="熔断失败阈值")
    circuit_breaker_timeout_seconds: int = Field(default=60, description="熔断恢复超时")

    # 评测配置
    evaluation_timeout: int = Field(default=30, description="评测超时秒数")
    max_concurrent_evaluations: int = Field(default=10, description="最大并发评测数")

    # OpenTelemetry
    otel_enabled: bool = Field(default=False, description="是否启用追踪")
    otel_service_name: str = Field(default="ai-eval-platform", description="服务名")
    otel_exporter_endpoint: str | None = Field(default=None, description="追踪导出端点")

    # Prometheus
    prometheus_enabled: bool = Field(default=True, description="是否启用指标")


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 便捷访问
settings = get_settings()
