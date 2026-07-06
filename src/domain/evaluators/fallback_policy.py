"""
🛡️ 统一的降级策略（Fallback Policy）
定义评估器在 LLM 不可用或熔断时的行为规则。
支持 2026 同步/异步高并发双轨制执行流，防止 CPU 密集型向量计算卡死主线程。

事件驱动集成：通过 EventBus 发布 FALLBACK_TRIGGERED 事件
"""

import asyncio
import logging
from abc import ABC
from abc import abstractmethod

from src.domain.services.text_analysis_service import text_analysis_service
from src.exceptions import DomainLogicError
from src.infra.event_bus import EventType
from src.infra.event_bus import publish_event

logger = logging.getLogger(__name__)


class FallbackPolicy(ABC):
    """降级策略抽象基类（支持双轨制契约）"""

    def __init__(self, allow_fallback: bool = True, fallback_method: str = "none"):
        self.allow_fallback = allow_fallback
        self.fallback_method = fallback_method

    @abstractmethod
    def should_fallback(self, error: Exception) -> bool:
        """判断是否应该降级"""
        pass

    @abstractmethod
    def get_fallback_score(self, actual_output: str, expected_output: str) -> float:
        """[同步轨] 获取降级分数"""
        pass

    @abstractmethod
    async def get_fallback_score_async(self, actual_output: str, expected_output: str) -> float:
        """🚀 [异步轨] 获取降级分数（实现非阻塞高并发）"""
        pass

    @abstractmethod
    def get_fallback_metadata(self) -> dict:
        """获取降级元数据"""
        pass

    def get_confidence(self) -> float:
        """获取降级结果的置信度"""
        return 0.5

    def _publish_fallback_event(self, actual_output: str, expected_output: str, score: float, error: Exception = None):
        """发布降级触发事件"""
        publish_event(
            EventType.FALLBACK_TRIGGERED,
            fallback_method=self.fallback_method,
            actual_output=actual_output[:200] if actual_output else "",
            expected_output=expected_output[:200] if expected_output else "",
            score=score,
            confidence=self.get_confidence(),
            error_message=str(error) if error else None,
            source=f"fallback_policy.{self.fallback_method}",
        )


class NoFallbackPolicy(FallbackPolicy):
    """禁止降级策略 - 严格任务专用

    适用于：对准确率有绝对洁癖、拒绝任何形式字面或向量兜底的任务。
    原则：宁可拒绝服务抛出异常，也绝不给出具有欺骗性的评估分数。
    """

    def __init__(self):
        super().__init__(allow_fallback=False, fallback_method="none")

    def should_fallback(self, error: Exception) -> bool:
        logger.warning(f"触发严格禁止降级策略，原始错误: {error}")
        return False

    def get_fallback_score(self, actual_output: str, expected_output: str) -> float:
        return 0.0

    async def get_fallback_score_async(self, actual_output: str, expected_output: str) -> float:
        return 0.0

    def get_fallback_metadata(self) -> dict:
        return {
            "mode": "fallback_denied",
            "confidence": 0.0,
            "warning": "该任务已被配置为硬性禁止降级，评估流中断",
        }

    def get_confidence(self) -> float:
        return 0.0


class EmbeddingFallbackPolicy(FallbackPolicy):
    """Embedding 降级策略 - 优先使用向量相似度

    降级路径：LLM 失败 ➔ Embedding 向量相似度 ➔ 拒绝服务
    """

    OPPOSITE_WORD_PAIRS = {
        ("好", "坏"), ("好", "差"), ("好", "糟"), ("好", "恶劣"), ("好", "不好"),
        ("满意", "不满"), ("满意", "失望"), ("满意", "不满意"),
        ("高", "低"), ("大", "小"), ("多", "少"),
        ("热", "冷"), ("湿", "干"), ("快", "慢"),
        ("会", "不会"), ("能", "不能"), ("可以", "不可以"),
        ("是", "不是"), ("有", "没有"), ("在", "不在"),
        ("正", "负"), ("积极", "消极"), ("正确", "错误"),
        ("成功", "失败"), ("安全", "危险"), ("正常", "异常"),
        ("喜欢", "讨厌"), ("爱", "恨"), ("美丽", "丑陋"),
        ("增加", "减少"), ("上升", "下降"), ("前进", "后退"),
        ("可行", "不可行"), ("可能", "不可能"), ("应该", "不应该"),
        ("同意", "不同意"), ("支持", "反对"), ("接受", "拒绝"),
        ("重要", "不重要"), ("有用", "没用"), ("有效", "无效"),
        ("简单", "复杂"), ("容易", "困难"), ("快速", "缓慢"),
    }

    def __init__(self):
        super().__init__(allow_fallback=True, fallback_method="embedding")

    def _detect_opposite_meaning(self, text1: str, text2: str) -> float:
        """检测语义相反程度，返回相反度分数 (0-1)"""
        if text_analysis_service.detect_opposite_meaning(text1, text2):
            return 1.0
        return 0.0

    def should_fallback(self, error: Exception) -> bool:
        return True

    def get_fallback_score(self, actual_output: str, expected_output: str) -> float:
        """[同步轨] 使用同步 Embedding 计算语义相似度"""
        try:
            from .embedding_service import EmbeddingService

            service = EmbeddingService.get_instance()

            if service.is_available():
                similarity = service.calculate_similarity(actual_output, expected_output)
                
                opposite_score = self._detect_opposite_meaning(actual_output, expected_output)
                if opposite_score > 0.5:
                    similarity = max(0.0, similarity - opposite_score * 0.8)
                
                score = max(0.0, float(similarity))
                logger.info(f"Embedding 同步降级计算完成，相似度: {similarity}，反义词检测: {opposite_score}")
                self._publish_fallback_event(actual_output, expected_output, score)
                return score
            else:
                logger.warning("Embedding 服务不可用，无法执行向量降级")
                return 0.0
        except Exception as e:
            logger.error(f"Embedding 同步降级链条发生异常: {e}")
            self._publish_fallback_event(actual_output, expected_output, 0.0, e)
            return 0.0

    async def get_fallback_score_async(self, actual_output: str, expected_output: str) -> float:
        """🚀 [异步轨] 将稠密的本地模型推理（或网络 I/O）隔离至线程池，绝不卡死主事件循环"""
        try:
            from .embedding_service import EmbeddingService

            service = EmbeddingService.get_instance()

            if not service.is_available():
                logger.warning("Embedding 服务在异步状态下不可用，拒绝服务")
                return 0.0

            if hasattr(service, "calculate_similarity_async"):
                similarity = await service.calculate_similarity_async(
                    actual_output, expected_output
                )
            else:
                similarity = await asyncio.to_thread(
                    service.calculate_similarity, actual_output, expected_output
                )
            
            opposite_score = self._detect_opposite_meaning(actual_output, expected_output)
            if opposite_score > 0.5:
                similarity = max(0.0, similarity - opposite_score * 0.8)

            score = max(0.0, float(similarity))
            logger.info(f"🚀 Embedding 异步隔离降级计算完成，相似度: {similarity}，反义词检测: {opposite_score}")
            self._publish_fallback_event(actual_output, expected_output, score)
            return score
        except Exception as e:
            logger.error(f"Embedding 异步降级链条发生异常: {e}")
            self._publish_fallback_event(actual_output, expected_output, 0.0, e)
            return 0.0

    def get_fallback_metadata(self) -> dict:
        return {
            "mode": "fallback_embedding",
            "confidence": 0.7,
            "warning": "大模型调用失败，系统已自动无缝切换为 [本地模型文本向量相似度] 降级评估",
        }

    def get_confidence(self) -> float:
        return 0.7


class KeywordFallbackPolicy(FallbackPolicy):
    """关键词匹配降级策略（适用于分类、正则、情感短文本等任务）"""

    def __init__(self):
        super().__init__(allow_fallback=True, fallback_method="keyword")

    def should_fallback(self, error: Exception) -> bool:
        return True

    def get_fallback_score(self, actual_output: str, expected_output: str) -> float:
        from .scoring import score_keyword_overlap

        score = float(score_keyword_overlap(actual_output, expected_output))
        self._publish_fallback_event(actual_output, expected_output, score)
        return score

    async def get_fallback_score_async(self, actual_output: str, expected_output: str) -> float:
        return self.get_fallback_score(actual_output, expected_output)

    def get_fallback_metadata(self) -> dict:
        return {
            "mode": "fallback_keyword",
            "confidence": 0.4,
            "warning": "使用关键词匹配降级评估，无法感知长文本语义，准确率偏低",
        }

    def get_confidence(self) -> float:
        return 0.4


class CharacterFallbackPolicy(FallbackPolicy):
    """字符相似度降级策略（🚨 严禁用于高级语义任务）"""

    def __init__(self):
        super().__init__(allow_fallback=True, fallback_method="character")

    def should_fallback(self, error: Exception) -> bool:
        return True

    def get_fallback_score(self, actual_output: str, expected_output: str) -> float:
        from .scoring import score_text_similarity

        score = float(score_text_similarity(actual_output, expected_output))
        self._publish_fallback_event(actual_output, expected_output, score)
        return score

    async def get_fallback_score_async(self, actual_output: str, expected_output: str) -> float:
        return self.get_fallback_score(actual_output, expected_output)

    def get_fallback_metadata(self) -> dict:
        return {
            "mode": "fallback_character",
            "confidence": 0.3,
            "warning": "⚠️ 正在使用纯字面编辑距离/Jaccard 降级，完全无法识别语义相反的文本！",
        }

    def get_confidence(self) -> float:
        return 0.3


class SemanticTaskPolicy(EmbeddingFallbackPolicy):
    """🧠 语义任务专用核心策略 - 熔断阻断与硬性规约

    1. 大模型优先；
    2. 大模型故障时平滑切换至 Embedding 向量相似度；
    3. 🚨 铁律：一旦 Embedding 也不可用，直接熔断并抛出领域逻辑错误，绝对禁止滑向字符字面相似度！
    """

    def __init__(self):
        super().__init__()

    def get_fallback_score(self, actual_output: str, expected_output: str) -> float:
        """同步硬性规约"""
        try:
            from .embedding_service import EmbeddingService

            service = EmbeddingService.get_instance()

            if service.is_available():
                similarity = service.calculate_similarity(actual_output, expected_output)
                
                opposite_score = self._detect_opposite_meaning(actual_output, expected_output)
                if opposite_score > 0.3:
                    similarity = max(0.0, similarity - opposite_score * 0.9)
                
                return max(0.0, float(similarity))
            else:
                logger.critical(
                    "🚨 [域安全拦截] Embedding 服务瘫痪，语义任务硬性拦截字符匹配降级！"
                )
                raise DomainLogicError(
                    "Embedding service unavailable. Fallback to character token-matching is strictly blocked."
                )
        except DomainLogicError:
            raise
        except Exception as e:
            logger.error(f"语义任务降级时发生未预料的底层错误: {e}")
            raise DomainLogicError(f"Semantic fallback chain broke down: {str(e)}") from e

    async def get_fallback_score_async(self, actual_output: str, expected_output: str) -> float:
        """🚀 异步高并发硬性规约"""
        try:
            from .embedding_service import EmbeddingService

            service = EmbeddingService.get_instance()

            if not service.is_available():
                logger.critical("🚨 [域安全拦截] 异步流中检测到 Embedding 服务不可用，紧急熔断！")
                raise DomainLogicError(
                    "Embedding service unavailable in async flow. Character fallback blocked."
                )

            if hasattr(service, "calculate_similarity_async"):
                similarity = await service.calculate_similarity_async(
                    actual_output, expected_output
                )
            else:
                similarity = await asyncio.to_thread(
                    service.calculate_similarity, actual_output, expected_output
                )
            
            opposite_score = self._detect_opposite_meaning(actual_output, expected_output)
            if opposite_score > 0.3:
                similarity = max(0.0, similarity - opposite_score * 0.9)

            return max(0.0, float(similarity))
        except DomainLogicError:
            raise
        except Exception as e:
            raise DomainLogicError(f"Async semantic fallback chain broke down: {str(e)}") from e


class StrictSemanticPolicy(NoFallbackPolicy):
    """严格语义策略 - 无论发生任何事情，完全禁止任何形式的降级"""

    def __init__(self):
        super().__init__()


class RuleBasedFallbackPolicy(FallbackPolicy):
    """规则引擎降级策略 - 基于规则的QA和事实性评估

    适用于：配置了_rule_based_qa或_rule_based_factuality方法的评估器
    """

    def __init__(self):
        super().__init__(allow_fallback=True, fallback_method="rule_based")

    def should_fallback(self, error: Exception) -> bool:
        return True

    def get_fallback_score(self, actual_output: str, expected_output: str, question: str = "") -> float:
        from src.domain.evaluators.base import BaseEvaluator

        evaluator = BaseEvaluator.get_current_evaluator()
        if evaluator is None:
            return 0.0

        score = 0.0

        if hasattr(evaluator, '_rule_based_qa') and callable(getattr(evaluator, '_rule_based_qa')):
            try:
                result = evaluator._rule_based_qa(question, actual_output, expected_output)
                if result is not None:
                    score = float(result)
            except Exception as e:
                logger.error(f"_rule_based_qa执行失败: {e}")
                self._publish_fallback_event(actual_output, expected_output, 0.0, e)
                return 0.0

        if score == 0.0 and hasattr(evaluator, '_rule_based_factuality') and callable(getattr(evaluator, '_rule_based_factuality')):
            try:
                result = evaluator._rule_based_factuality(actual_output, expected_output)
                if result is not None:
                    score = float(result)
            except Exception as e:
                logger.error(f"_rule_based_factuality执行失败: {e}")
                self._publish_fallback_event(actual_output, expected_output, 0.0, e)
                return 0.0

        self._publish_fallback_event(actual_output, expected_output, score)
        return score

    async def get_fallback_score_async(self, actual_output: str, expected_output: str, question: str = "") -> float:
        return self.get_fallback_score(actual_output, expected_output, question)

    def get_fallback_metadata(self) -> dict:
        return {
            "mode": "fallback_rule_based",
            "confidence": 0.6,
            "warning": "使用规则引擎降级评估，基于预定义规则进行判断",
        }

    def get_confidence(self) -> float:
        return 0.6


class FallbackPolicyFactory:
    """降级策略工厂"""

    POLICY_MAP = {
        "none": NoFallbackPolicy,
        "embedding": EmbeddingFallbackPolicy,
        "keyword": KeywordFallbackPolicy,
        "character": CharacterFallbackPolicy,
        "semantic_task": SemanticTaskPolicy,
        "strict_semantic": StrictSemanticPolicy,
        "rule_based": RuleBasedFallbackPolicy,
    }

    @classmethod
    def get_policy(cls, policy_type: str) -> FallbackPolicy:
        policy_class = cls.POLICY_MAP.get(policy_type)
        if policy_class is None:
            raise ValueError(f"未知的降级策略类型: {policy_type}")
        return policy_class()
