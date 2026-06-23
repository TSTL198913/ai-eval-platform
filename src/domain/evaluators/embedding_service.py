"""
🧠 Embedding 服务 - 统一的向量相似度计算引擎
支持 Sentence-BERT 和 BGE-M3 模型，提供高并发、非阻塞语义级相似度计算。
完美适配 2026 异步高并发双轨制，隔离 PyTorch 推理计算，防止卡死事件循环。
"""

import asyncio
import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

try:
    import torch
    from sentence_transformers import SentenceTransformer, util

    HAS_EMBEDDING = True
except ImportError:
    HAS_EMBEDDING = False
    logger.warning("🚨 未安装 sentence-transformers，Embedding 服务将不可用")

if TYPE_CHECKING:
    import torch


class EmbeddingService:
    """统一的向量嵌入服务（支持同步/异步高性能双轨制）

    支持模型：
    - BAAI/bge-m3 (推荐): 多粒度嵌入，支持中文，效果最好
    - all-MiniLM-L6-v2: 轻量级，速度快，支持多语言
    - paraphrase-multilingual-MiniLM-L12-v2: 多语言优化版
    """

    DEFAULT_MODEL = "BAAI/bge-m3"
    MINI_MODEL = "all-MiniLM-L6-v2"
    MULTILINGUAL_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

    _instance = None
    _lock = None

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = "auto"):
        """初始化 Embedding 服务"""
        if not HAS_EMBEDDING:
            self.model = None
            return

        self.model_name = model_name
        self.device = device
        self._load_model()

    def _load_model(self):
        """加载预训练模型"""
        try:
            if self.device == "auto":
                self.device = (
                    "cuda" if (torch.cuda.is_available() and hasattr(torch, "cuda")) else "cpu"
                )

            # 模型加载属于重度 I/O 和计算，保持同步加载，由框架在冷启动时完成
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(
                f"✨ Embedding 服务已成功加载模型: {self.model_name} (运行设备: {self.device})"
            )
        except Exception as e:
            logger.critical(f"🚨 严重错误：加载 Embedding 模型失败: {e}", exc_info=True)
            self.model = None

    def is_available(self) -> bool:
        """检查 Embedding 服务是否可用"""
        return HAS_EMBEDDING and self.model is not None

    # ==================== 🚄 1. 同步执行流（向后兼容传统评测流） ====================

    def encode(self, texts: list[str], **kwargs) -> "torch.Tensor":
        """[同步轨] 将文本编码为向量矩阵"""
        if not self.is_available():
            raise RuntimeError(
                "Embedding 服务当前不可用，请检查 sentence-transformers 依赖或模型加载日志"
            )
        return self.model.encode(texts, **kwargs)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """[同步轨] 计算两段文本的语义余弦相似度"""
        if not self.is_available():
            raise RuntimeError("Embedding 服务当前不可用")

        embeddings = self.model.encode([text1, text2])
        similarity = util.cos_sim(embeddings[0], embeddings[1])
        return float(similarity.item())

    def calculate_similarity_batch(self, texts: list[str], targets: list[str]) -> list[float]:
        """[同步轨] 批量一对一计算文本对的语义相似度"""
        if not self.is_available():
            raise RuntimeError("Embedding 服务当前不可用")

        if len(texts) != len(targets):
            raise ValueError("⚡ 批量相似度计算失败：texts 和 targets 列表长度必须严格一致")

        text_embeddings = self.model.encode(texts)
        target_embeddings = self.model.encode(targets)
        similarities = util.cos_sim(text_embeddings, target_embeddings)

        return [float(similarities[i][i].item()) for i in range(len(texts))]

    # ==================== 🚀 2. 异步执行流（2026 高并发引擎专属核心） ====================

    async def encode_async(self, texts: list[str], **kwargs) -> "torch.Tensor":
        """🚀 [异步轨] 非阻塞式文本向量化（将 CPU/GPU 推理卸载至线程池）"""
        if not self.is_available():
            raise RuntimeError("Embedding 服务当前不可用")
        # 完美利用 asyncio.to_thread 榨干多核多线程性能，同时保障主事件循环绝对流畅
        return await asyncio.to_thread(self.encode, texts, **kwargs)

    async def calculate_similarity_async(self, text1: str, text2: str) -> float:
        """🚀 [异步轨] 非阻塞式单对语义相似度计算（完美满足 FallbackPolicy 契约）"""
        if not self.is_available():
            raise RuntimeError("Embedding 服务当前不可用")
        return await asyncio.to_thread(self.calculate_similarity, text1, text2)

    async def calculate_similarity_batch_async(
        self, texts: list[str], targets: list[str]
    ) -> list[float]:
        """🚀 [异步轨] 非阻塞式批量语义相似度计算"""
        if not self.is_available():
            raise RuntimeError("Embedding 服务当前不可用")
        return await asyncio.to_thread(self.calculate_similarity_batch, texts, targets)

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        """获取线程安全的单例实例"""
        if cls._lock is None:
            import threading

            cls._lock = threading.Lock()

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = EmbeddingService()
        return cls._instance
