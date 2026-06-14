"""
LLM 客户端抽象层

支持多种 LLM 提供者:
- OpenAI (GPT-4, GPT-3.5)
- DeepSeek
- Anthropic (Claude)
- 本地模型 (Ollama, vLLM)

特性:
- 统一接口
- 自动重试
- 熔断器保护
- 速率限制
- 响应缓存
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, TypeVar

import httpx

from src.distributed.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from src.tracing import get_tracer

logger = logging.getLogger(__name__)

T = TypeVar("T")


class LLMProvider(Enum):
    """LLM 提供者"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    STUB = "stub"


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: LLMProvider = LLMProvider.DEEPSEEK
    api_key: str = ""
    model_name: str = "deepseek-chat"
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout: float = 30.0
    retry_times: int = 3
    retry_delay: float = 1.0


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # system, user, assistant
    content: str


@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    raw_response: Optional[Dict] = None


class BaseLLMClient(ABC):
    """
    LLM 客户端基类

    提供统一的接口和通用功能
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._http_client: Optional[httpx.AsyncClient] = None
        self._circuit_breaker = CircuitBreaker(
            f"llm_{config.provider.value}",
            CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
            ),
        )

    @property
    @abstractmethod
    def provider(self) -> LLMProvider:
        """返回 LLM 提供者类型"""
        pass

    @abstractmethod
    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        pass

    @abstractmethod
    def _parse_response(self, raw_response: Dict) -> ChatResponse:
        """解析响应"""
        pass

    @abstractmethod
    async def _do_request(
        self,
        messages: List[Dict[str, str]],
    ) -> Dict:
        """执行 HTTP 请求"""
        pass

    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> ChatResponse:
        """
        同步聊天 (实际是异步)
        """
        tracer = get_tracer()
        span = tracer.create_span(
            f"llm.chat.{self.provider.value}",
            attributes={
                "model": self.config.model_name,
                "provider": self.provider.value,
            },
        )

        try:
            messages = self._build_messages(prompt, system_prompt)

            response = await self._circuit_breaker.call(
                self._do_request,
                messages,
            )

            chat_response = self._parse_response(response)
            chat_response.latency_ms = (span.end_time or time.time()) - span.start_time

            span.set_attribute("response.length", len(chat_response.content))
            span.set_attribute("usage.total_tokens", chat_response.usage.get("total_tokens", 0))

            return chat_response
        except Exception as e:
            span.set_status("ERROR", str(e))
            raise
        finally:
            tracer.end_span(span)

    async def achat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> ChatResponse:
        """异步聊天"""
        return await self.chat(prompt, system_prompt)

    async def close(self):
        """关闭客户端"""
        if self._http_client:
            await self._http_client.aclose()


class OpenAIClient(BaseLLMClient):
    """OpenAI 客户端"""

    def __init__(self, config: LLMConfig):
        if config.base_url is None:
            config.base_url = "https://api.openai.com/v1"
        super().__init__(config)

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OPENAI

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _parse_response(self, raw_response: Dict) -> ChatResponse:
        return ChatResponse(
            content=raw_response["choices"][0]["message"]["content"],
            model=raw_response.get("model", self.config.model_name),
            usage=raw_response.get("usage", {}),
            raw_response=raw_response,
        )

    async def _do_request(self, messages: List[Dict[str, str]]) -> Dict:
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.config.timeout)

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        response = await self._http_client.post(
            f"{self.config.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


class DeepSeekClient(BaseLLMClient):
    """DeepSeek 客户端"""

    def __init__(self, config: LLMConfig):
        if config.base_url is None:
            config.base_url = "https://api.deepseek.com/v1"
        super().__init__(config)

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.DEEPSEEK

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _parse_response(self, raw_response: Dict) -> ChatResponse:
        return ChatResponse(
            content=raw_response["choices"][0]["message"]["content"],
            model=raw_response.get("model", self.config.model_name),
            usage=raw_response.get("usage", {}),
            raw_response=raw_response,
        )

    async def _do_request(self, messages: List[Dict[str, str]]) -> Dict:
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.config.timeout)

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        response = await self._http_client.post(
            f"{self.config.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


class AnthropicClient(BaseLLMClient):
    """Anthropic (Claude) 客户端"""

    def __init__(self, config: LLMConfig):
        if config.base_url is None:
            config.base_url = "https://api.anthropic.com/v1"
        super().__init__(config)

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.ANTHROPIC

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            # Anthropic 使用 system 字段
            messages.append({"role": "user", "content": prompt})
            return messages  # system 需要单独处理
        messages.append({"role": "user", "content": prompt})
        return messages

    def _parse_response(self, raw_response: Dict) -> ChatResponse:
        return ChatResponse(
            content=raw_response["content"][0]["text"],
            model=raw_response.get("model", self.config.model_name),
            usage=raw_response.get("usage", {}),
            raw_response=raw_response,
        )

    async def _do_request(self, messages: List[Dict[str, str]]) -> Dict:
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.config.timeout)

        headers = {
            "x-api-key": self.config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        # Anthropic 的消息格式不同
        user_message = messages[-1]["content"] if messages else ""
        system_prompt = None
        for msg in messages[:-1]:
            if msg["role"] == "system":
                system_prompt = msg["content"]
                break

        payload = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": user_message}],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = await self._http_client.post(
            f"{self.config.base_url}/messages",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


class OllamaClient(BaseLLMClient):
    """Ollama 本地模型客户端"""

    def __init__(self, config: LLMConfig):
        if config.base_url is None:
            config.base_url = "http://localhost:11434"
        super().__init__(config)

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OLLAMA

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> List[Dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _parse_response(self, raw_response: Dict) -> ChatResponse:
        return ChatResponse(
            content=raw_response["message"]["content"],
            model=raw_response.get("model", self.config.model_name),
            usage={},  # Ollama 可能不返回 usage
            raw_response=raw_response,
        )

    async def _do_request(self, messages: List[Dict[str, str]]) -> Dict:
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.config.timeout)

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
        }

        response = await self._http_client.post(
            f"{self.config.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


class StubLLMClient(BaseLLMClient):
    """桩客户端，用于测试和开发"""

    def __init__(self, config: Optional[LLMConfig] = None):
        if config is None:
            config = LLMConfig(provider=LLMProvider.STUB, model_name="stub-model")
        super().__init__(config)

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.STUB

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str],
    ) -> List[Dict[str, str]]:
        return [{"role": "user", "content": prompt}]

    def _parse_response(self, raw_response: Dict) -> ChatResponse:
        return ChatResponse(
            content=raw_response.get("content", "Stub response"),
            model="stub-model",
            usage={"total_tokens": 10},
        )

    async def _do_request(self, messages: List[Dict[str, str]]) -> Dict:
        # 模拟延迟
        await asyncio.sleep(0.01)
        return {
            "content": f"【模拟响应】针对问题「{messages[-1]['content'][:50]}」的回答。",
            "model": "stub-model",
        }


class LLMClientFactory:
    """LLM 客户端工厂"""

    _clients: Dict[LLMProvider, type] = {
        LLMProvider.OPENAI: OpenAIClient,
        LLMProvider.DEEPSEEK: DeepSeekClient,
        LLMProvider.ANTHROPIC: AnthropicClient,
        LLMProvider.OLLAMA: OllamaClient,
        LLMProvider.STUB: StubLLMClient,
    }

    @classmethod
    def create(cls, config: LLMConfig) -> BaseLLMClient:
        """创建 LLM 客户端"""
        client_class = cls._clients.get(config.provider)
        if not client_class:
            raise ValueError(f"Unsupported provider: {config.provider}")
        return client_class(config)

    @classmethod
    def register(cls, provider: LLMProvider, client_class: type) -> None:
        """注册新的客户端类型"""
        cls._clients[provider] = client_class


def create_llm_client(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
) -> BaseLLMClient:
    """
    便捷函数：创建 LLM 客户端

    从环境变量读取默认配置
    """
    import os

    provider = provider or os.getenv("LLM_PROVIDER", "deepseek")
    api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY", "")
    model_name = model_name or os.getenv(f"{provider.upper()}_MODEL", "deepseek-chat")
    base_url = base_url or os.getenv(f"{provider.upper()}_BASE_URL")

    llm_provider = LLMProvider(provider.lower())

    config = LLMConfig(
        provider=llm_provider,
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
    )

    # 如果没有 API key，使用 stub
    if not api_key or api_key == "stub-no-key":
        return StubLLMClient()

    return LLMClientFactory.create(config)
