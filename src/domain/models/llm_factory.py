"""
LLM 客户端工厂 - 智能模型接入

支持一键接入多种AI模型：
- 自动检测环境变量配置
- 内置主流模型支持
- 简单配置即可切换模型
- 客户端单例缓存与池化管理
"""

import os
import threading
from typing import Dict, Optional

from src.domain.models.base import BaseLLMClient, ModelConfig


# ============================================================================
# 缓存管理 - 减少重复创建和环境变量读取
# ============================================================================

# 客户端单例缓存：key = "provider:model_name"
_llm_client_cache: Dict[str, BaseLLMClient] = {}

# 环境变量配置缓存：减少重复读取
_env_config_cache: Dict[str, ModelConfig] = {}

# 缓存锁：保证并发安全
_cache_lock = threading.RLock()
_env_cache_lock = threading.RLock()


class ModelProvider:
    """模型提供者枚举"""

    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    QWEN = "qwen"
    DASHSCOPE = "dashscope"
    CUSTOM = "custom"


class ModelRegistry:
    """模型注册中心"""

    _registry: dict[str, type[BaseLLMClient]] = {}

    @classmethod
    def register(cls, provider: str):
        """注册模型客户端类"""

        def decorator(client_class: type[BaseLLMClient]):
            cls._registry[provider.lower()] = client_class
            return client_class

        return decorator

    @classmethod
    def get_client_class(cls, provider: str) -> type[BaseLLMClient] | None:
        """获取模型客户端类"""
        return cls._registry.get(provider.lower())

    @classmethod
    def list_providers(cls) -> list[str]:
        """列出所有支持的模型提供者"""
        return list(cls._registry.keys())


def load_config(provider: str | None = None, use_cache: bool = True) -> ModelConfig:
    """
    智能加载模型配置

    根据环境变量自动配置，支持多种模型提供者：
    - DeepSeek: DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL
    - OpenAI: OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
    - Anthropic: ANTHROPIC_API_KEY, ANTHROPIC_MODEL
    - Ollama: OLLAMA_MODEL, OLLAMA_BASE_URL
    - Qwen/DashScope: DASHSCOPE_API_KEY, DASHSCOPE_MODEL

    Args:
        provider: 模型提供者，为空则从环境变量 LLM_PROVIDER 读取
        use_cache: 是否使用缓存，默认 True

    Returns:
        ModelConfig: 模型配置对象
    """
    # 自动检测提供者
    provider = provider or os.getenv("LLM_PROVIDER", ModelProvider.DEEPSEEK).lower()
    cache_key = provider

    # 检查缓存
    if use_cache:
        with _env_cache_lock:
            if cache_key in _env_config_cache:
                return _env_config_cache[cache_key]

    # 根据提供者加载配置
    config_map = {
        ModelProvider.DEEPSEEK: {
            "api_key_env": "DEEPSEEK_API_KEY",
            "model_env": "DEEPSEEK_MODEL",
            "base_url_env": "DEEPSEEK_BASE_URL",
            "default_model": "deepseek-chat",
        },
        ModelProvider.OPENAI: {
            "api_key_env": "OPENAI_API_KEY",
            "model_env": "OPENAI_MODEL",
            "base_url_env": "OPENAI_BASE_URL",
            "default_model": "gpt-3.5-turbo",
        },
        ModelProvider.ANTHROPIC: {
            "api_key_env": "ANTHROPIC_API_KEY",
            "model_env": "ANTHROPIC_MODEL",
            "base_url_env": None,
            "default_model": "claude-3-sonnet-20240229",
        },
        ModelProvider.OLLAMA: {
            "api_key_env": None,  # Ollama 不需要 API Key
            "model_env": "OLLAMA_MODEL",
            "base_url_env": "OLLAMA_BASE_URL",
            "default_model": "llama3",
        },
        ModelProvider.QWEN: {
            "api_key_env": "DASHSCOPE_API_KEY",
            "model_env": "DASHSCOPE_MODEL",
            "base_url_env": None,
            "default_model": "qwen-max",
        },
        ModelProvider.DASHSCOPE: {
            "api_key_env": "DASHSCOPE_API_KEY",
            "model_env": "DASHSCOPE_MODEL",
            "base_url_env": None,
            "default_model": "qwen-max",
        },
    }

    config_info = config_map.get(provider)
    if not config_info:
        raise ValueError(f"不支持的模型提供者: {provider}。支持的提供者: {list(config_map.keys())}")

    # 读取配置
    api_key = os.getenv(config_info["api_key_env"], "") if config_info["api_key_env"] else ""
    model_name = os.getenv(config_info["model_env"], config_info["default_model"])
    base_url = os.getenv(config_info["base_url_env"]) if config_info["base_url_env"] else None

    config = ModelConfig(
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
    )

    # 缓存配置
    if use_cache:
        with _env_cache_lock:
            _env_config_cache[cache_key] = config

    return config


def _generate_cache_key(provider: str, config: ModelConfig | None) -> str:
    """生成缓存键"""
    if config:
        return f"{provider}:{config.model_name}"
    return f"{provider}:default"


def _create_new_client(provider: str, config: ModelConfig) -> BaseLLMClient:
    """
    创建新的 LLM 客户端实例

    Args:
        provider: 模型提供者
        config: 模型配置

    Returns:
        BaseLLMClient: 新创建的客户端实例
    """
    # 如果没有 API Key 或 API Key 是占位符且不是 Ollama，使用 Stub
    api_key_value = config.api_key.get_secret_value() if config.api_key else ""
    is_placeholder = api_key_value.startswith("your_") and api_key_value.endswith("_here")
    if (not api_key_value or is_placeholder) and provider != ModelProvider.OLLAMA:
        from src.domain.models.stub import StubLLMClient

        return StubLLMClient(ModelConfig(api_key="stub", model_name="stub-model"))

    # 获取客户端类
    client_class = ModelRegistry.get_client_class(provider)
    if not client_class:
        raise ValueError(
            f"未找到提供者 '{provider}' 的客户端实现。\n"
            f"已注册的提供者: {ModelRegistry.list_providers()}\n"
            f"如需添加新模型，请使用 @ModelRegistry.register('provider_name') 装饰器"
        )

    return client_class(config)


def create_llm_client(
    provider: str | None = None,
    config: ModelConfig | None = None,
    client: BaseLLMClient | None = None,
    use_cache: bool = True,
) -> BaseLLMClient:
    """
    一键创建 LLM 客户端（带缓存）

    使用方式：
    1. 最简单：create_llm_client() - 自动从环境变量读取配置
    2. 指定提供者：create_llm_client(provider="openai")
    3. 自定义配置：create_llm_client(config=ModelConfig(...))
    4. 注入客户端：create_llm_client(client=MockClient()) - 用于测试
    5. 禁用缓存：create_llm_client(use_cache=False) - 每次创建新实例

    环境变量配置示例：
    LLM_PROVIDER=openai
    OPENAI_API_KEY=your-key
    OPENAI_MODEL=gpt-4o

    Args:
        provider: 模型提供者，为空则从环境变量读取
        config: 自定义模型配置
        client: 直接注入客户端（测试用）
        use_cache: 是否使用缓存，默认 True

    Returns:
        BaseLLMClient: LLM 客户端实例
    """
    # 测试模式：直接注入客户端（不缓存）
    if client is not None:
        return client

    # 确定提供者
    provider = provider or os.getenv("LLM_PROVIDER", ModelProvider.DEEPSEEK).lower()

    # 使用自定义配置（不缓存）
    if config is not None:
        client_class = ModelRegistry.get_client_class(provider)
        if client_class:
            return client_class(config)
        raise ValueError(f"未注册的提供者: {provider}")

    # 生成缓存键
    cache_key = _generate_cache_key(provider, config)

    # 使用缓存时的原子操作：检查-创建-缓存
    if use_cache:
        with _cache_lock:
            # 双重检查：先检查缓存
            if cache_key in _llm_client_cache:
                return _llm_client_cache[cache_key]

            # 加载配置并创建客户端（在锁内执行）
            loaded_config = load_config(provider, use_cache=True)
            new_client = _create_new_client(provider, loaded_config)

            # 缓存客户端
            _llm_client_cache[cache_key] = new_client
            return new_client

    # 不使用缓存：直接创建
    loaded_config = load_config(provider, use_cache=False)
    return _create_new_client(provider, loaded_config)


def validate_config() -> dict:
    """
    验证当前配置是否有效

    返回：{
        "valid": bool,
        "provider": str,
        "model": str,
        "errors": list[str],
        "warnings": list[str]
    }
    """
    result = {
        "valid": True,
        "provider": None,
        "model": None,
        "errors": [],
        "warnings": [],
    }

    try:
        provider = os.getenv("LLM_PROVIDER", ModelProvider.DEEPSEEK).lower()
        result["provider"] = provider

        if provider not in ModelRegistry.list_providers():
            result["valid"] = False
            result["errors"].append(f"未知的模型提供者: {provider}")
            return result

        config = load_config(provider)
        result["model"] = config.model_name

        # 检查 API Key（Ollama 除外）
        if provider != ModelProvider.OLLAMA:
            api_key = config.api_key.get_secret_value()
            if not api_key or api_key == "your_api_key_here":
                result["warnings"].append(f"未配置 {provider.upper()} API Key，将使用模拟客户端")

        return result

    except Exception as e:
        result["valid"] = False
        result["errors"].append(str(e))
        return result


# ============================================================================
# 缓存池管理 API
# ============================================================================


def get_cached_client(provider: str, model_name: str | None = None) -> BaseLLMClient | None:
    """
    获取已缓存的客户端（不创建新客户端）

    Args:
        provider: 模型提供者
        model_name: 模型名称，为空则使用 default

    Returns:
        BaseLLMClient | None: 缓存的客户端，不存在则返回 None
    """
    cache_key = f"{provider}:{model_name}" if model_name else f"{provider}:default"
    with _cache_lock:
        return _llm_client_cache.get(cache_key)


def clear_client_cache(provider: str | None = None) -> int:
    """
    清除客户端缓存

    Args:
        provider: 指定提供者则只清除该提供者的缓存，为空则清除所有

    Returns:
        int: 清除的缓存数量
    """
    with _cache_lock:
        if provider is None:
            count = len(_llm_client_cache)
            _llm_client_cache.clear()
            return count
        else:
            keys_to_remove = [k for k in _llm_client_cache if k.startswith(f"{provider}:")]
            for key in keys_to_remove:
                del _llm_client_cache[key]
            return len(keys_to_remove)


def clear_env_config_cache(provider: str | None = None) -> int:
    """
    清除环境变量配置缓存

    Args:
        provider: 指定提供者则只清除该提供者的缓存，为空则清除所有

    Returns:
        int: 清除的缓存数量
    """
    with _env_cache_lock:
        if provider is None:
            count = len(_env_config_cache)
            _env_config_cache.clear()
            return count
        else:
            if provider in _env_config_cache:
                del _env_config_cache[provider]
                return 1
            return 0


def clear_all_caches() -> dict:
    """
    清除所有缓存（客户端和环境变量配置）

    Returns:
        dict: 清除统计 {"clients": int, "env_configs": int}
    """
    with _cache_lock:
        client_count = len(_llm_client_cache)
        _llm_client_cache.clear()

    with _env_cache_lock:
        env_count = len(_env_config_cache)
        _env_config_cache.clear()

    return {"clients": client_count, "env_configs": env_count}


def get_cache_stats() -> dict:
    """
    获取缓存统计信息

    Returns:
        dict: 缓存统计 {"client_count": int, "env_config_count": int, "cached_providers": list}
    """
    with _cache_lock:
        client_count = len(_llm_client_cache)
        cached_providers = list(set(k.split(":")[0] for k in _llm_client_cache.keys()))

    with _env_cache_lock:
        env_count = len(_env_config_cache)

    return {
        "client_count": client_count,
        "env_config_count": env_count,
        "cached_providers": cached_providers,
    }


# 自动注册内置客户端
try:
    from src.domain.models.deepseek import DeepSeekClient

    ModelRegistry.register(ModelProvider.DEEPSEEK)(DeepSeekClient)
except ImportError:
    pass

try:
    from src.domain.models.openai import OpenAIClient

    ModelRegistry.register(ModelProvider.OPENAI)(OpenAIClient)
except ImportError:
    pass

try:
    from src.domain.models.anthropic import AnthropicClient

    ModelRegistry.register(ModelProvider.ANTHROPIC)(AnthropicClient)
except ImportError:
    pass

try:
    from src.domain.models.ollama import OllamaClient

    ModelRegistry.register(ModelProvider.OLLAMA)(OllamaClient)
except ImportError:
    pass

try:
    from src.domain.models.qwen import QwenClient

    ModelRegistry.register(ModelProvider.QWEN)(QwenClient)
    ModelRegistry.register(ModelProvider.DASHSCOPE)(QwenClient)
except ImportError:
    pass
