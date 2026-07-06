"""
客户端工厂服务：统一管理 LLM 客户端创建逻辑

职责：
- 提供统一的客户端创建入口
- 支持评估模型和推理模型的分别配置
- 封装模型路由决策逻辑
- 消除代码重复
"""

import logging
from typing import Optional
from typing import Tuple

from src.domain.model_routing import model_router
from src.domain.models.llm_factory import create_llm_client
from src.domain.models.llm_factory import load_config

logger = logging.getLogger(__name__)


class ClientFactoryService:
    """统一客户端工厂服务"""

    @staticmethod
    def create_eval_client(
        model_provider: Optional[str],
        model_name: Optional[str],
        evaluator_type: str,
        payload: dict
    ) -> Tuple[any, Optional[dict]]:
        """创建评估器客户端
        
        Args:
            model_provider: 模型提供者
            model_name: 模型名称
            evaluator_type: 评估器类型（用于路由决策）
            payload: 请求负载（用于路由决策）
            
        Returns:
            Tuple[client, routing_decision]: (客户端实例, 路由决策信息)
        """
        routing_decision = None

        if model_provider:
            config = load_config(model_provider)
            if model_name:
                config = config.model_copy(update={"model_name": model_name})
            client = create_llm_client(provider=model_provider, config=config)
            logger.info(f"创建评估客户端: {model_provider}/{model_name}")
        else:
            client, routing_decision = model_router.create_llm_client(evaluator_type, payload)
            logger.info(f"通过路由创建评估客户端: {routing_decision}")

        return client, routing_decision

    @staticmethod
    def create_inference_client(
        model_provider: Optional[str],
        model_name: Optional[str]
    ) -> Optional[any]:
        """创建推理客户端
        
        Args:
            model_provider: 模型提供者
            model_name: 模型名称
            
        Returns:
            client: 客户端实例（无配置时返回 None）
        """
        if not model_provider:
            return None

        config = load_config(model_provider)
        if model_name:
            config = config.model_copy(update={"model_name": model_name})
        client = create_llm_client(provider=model_provider, config=config)
        logger.info(f"创建推理客户端: {model_provider}/{model_name}")
        return client

    @staticmethod
    def create_clients(
        eval_model_provider: Optional[str],
        eval_model_name: Optional[str],
        inference_model_provider: Optional[str],
        inference_model_name: Optional[str],
        evaluator_type: str,
        payload: dict
    ) -> Tuple[any, Optional[any], Optional[dict]]:
        """创建评估和推理客户端
        
        Args:
            eval_model_provider: 评估模型提供者
            eval_model_name: 评估模型名称
            inference_model_provider: 推理模型提供者
            inference_model_name: 推理模型名称
            evaluator_type: 评估器类型
            payload: 请求负载
            
        Returns:
            Tuple[eval_client, inference_client, routing_decision]
        """
        eval_client, routing_decision = ClientFactoryService.create_eval_client(
            eval_model_provider, eval_model_name, evaluator_type, payload
        )
        inference_client = ClientFactoryService.create_inference_client(
            inference_model_provider, inference_model_name
        )
        return eval_client, inference_client, routing_decision