"""
LLM 客户端工厂 - 智能模型接入

支持一键接入多种AI模型：
- 自动检测环境变量配置
- 内置主流模型支持
- 简单配置即可切换模型
"""

import os

from src.domain.models.base import BaseLLMClient, ModelConfig


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


def load_config(provider: str | None = None) -> ModelConfig:
    """
    智能加载模型配置

    根据环境变量自动配置，支持多种模型提供者：
    - DeepSeek: DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL
    - OpenAI: OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
    - Anthropic: ANTHROPIC_API_KEY, ANTHROPIC_MODEL
    - Ollama: OLLAMA_MODEL, OLLAMA_BASE_URL
    - Qwen/DashScope: DASHSCOPE_API_KEY, DASHSCOPE_MODEL
    """
    # 自动检测提供者
    provider = provider or os.getenv("LLM_PROVIDER", ModelProvider.DEEPSEEK).lower()

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

    return ModelConfig(
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
    )


def create_llm_client(
    provider: str | None = None,
    config: ModelConfig | None = None,
    client: BaseLLMClient | None = None,
) -> BaseLLMClient:
    """
    一键创建 LLM 客户端

    使用方式：
    1. 最简单：create_llm_client() - 自动从环境变量读取配置
    2. 指定提供者：create_llm_client(provider="openai")
    3. 自定义配置：create_llm_client(config=ModelConfig(...))
    4. 注入客户端：create_llm_client(client=MockClient()) - 用于测试

    环境变量配置示例：
    LLM_PROVIDER=openai
    OPENAI_API_KEY=your-key
    OPENAI_MODEL=gpt-4o
    """
    # 测试模式：直接注入客户端
    if client is not None:
        return client

    # 使用自定义配置
    if config is not None:
        provider = provider or os.getenv("LLM_PROVIDER", ModelProvider.DEEPSEEK).lower()
        client_class = ModelRegistry.get_client_class(provider)
        if client_class:
            return client_class(config)
        raise ValueError(f"未注册的提供者: {provider}")

    # 从环境变量加载配置
    config = load_config(provider)
    provider = provider or os.getenv("LLM_PROVIDER", ModelProvider.DEEPSEEK).lower()

    # 如果没有 API Key 且不是 Ollama，使用 Stub
    if not config.api_key.get_secret_value() and provider != ModelProvider.OLLAMA:
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
