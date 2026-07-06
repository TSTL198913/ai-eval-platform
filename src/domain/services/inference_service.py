import asyncio
from typing import Optional

from loguru import logger

from src.domain.models.base import BaseLLMClient


class InferenceService:
    """独立推理服务：负责生成 actual_output
    
    职责：
    - 执行 LLM 推理，生成模型输出
    - 支持同步和异步推理
    - 记录推理耗时和 Token 使用
    """

    def __init__(self, client: BaseLLMClient):
        self.client = client

    def generate(self, prompt: str) -> str:
        """同步生成推理结果
        
        Args:
            prompt: 输入提示
            
        Returns:
            str: 模型生成的输出
        """
        logger.debug(f"推理服务 | 同步生成 | prompt_length={len(prompt)}")
        return self.client.chat(prompt)

    async def generate_async(self, prompt: str) -> str:
        """异步生成推理结果
        
        Args:
            prompt: 输入提示
            
        Returns:
            str: 模型生成的输出
        """
        logger.debug(f"推理服务 | 异步生成 | prompt_length={len(prompt)}")
        
        if hasattr(self.client, "achat"):
            return await self.client.achat(prompt)
        else:
            return await asyncio.to_thread(self.client.chat, prompt)

    @property
    def model_name(self) -> Optional[str]:
        """获取当前推理模型名称"""
        if self.client and self.client.config:
            return getattr(self.client.config, "model_name", None)
        return None

    @property
    def model_provider(self) -> Optional[str]:
        """获取当前推理模型提供者"""
        if self.client and self.client.config:
            return getattr(self.client.config, "provider", None)
        return None