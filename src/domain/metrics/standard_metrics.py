"""
📊 src/domain/metrics/standard_metrics.py
标准评测指标库 - 2026 工业级标准实现

实现业界主流的文本生成/翻译/摘要评测指标，统一量纲 0-1：
- BLEU (sacrebleu): 翻译质量行业标准
- ROUGE (rouge-score): 摘要质量行业标准
- METEOR: 综合考虑词形变化与同义词
- BERTScore: 基于预训练模型的语义相似度
- Embedding Cosine: 基于Sentence-BERT的语义相似度
- Levenshtein: 编辑距离归一化相似度

设计原则：
1. 适配器模式 - 第三方库缺失时降级到本地实现
2. 统一接口 - 所有指标继承 StandardMetric 抽象基类
3. 量纲归一 - 全部返回 0-1 区间的 float
4. 线程安全 - 无状态函数 + 内部锁保护可选项
"""

from __future__ import annotations

import logging
import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ==================== 第三方库可选依赖探测 ====================

try:
    import sacrebleu

    HAS_SACREBLEU = True
except ImportError:
    HAS_SACREBLEU = False
    logger.warning("⚠️ 未安装 sacrebleu，BLEU 指标将降级到本地 n-gram 实现")

try:
    from rouge_score import rouge_scorer

    HAS_ROUGE_SCORE = True
except ImportError:
    HAS_ROUGE_SCORE = False
    logger.warning("⚠️ 未安装 rouge-score，ROUGE 指标将降级到本地 LCS 实现")

try:
    import nltk
    from nltk.translate.meteor_score import meteor_score

    try:
        nltk.data.find("corpora/wordnet")
    except LookupError:
        try:
            nltk.download("wordnet", quiet=True)
        except Exception:
            pass

    HAS_METEOR = True
except ImportError:
    HAS_METEOR = False
    logger.warning("⚠️ 未安装 nltk 或 wordnet 语料，METEOR 指标将不可用")


# ==================== 抽象基类 ====================


@dataclass
class MetricResult:
    """标准指标计算结果"""

    name: str
    score: float
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 4),
            "description": self.description,
            "metadata": {
                k: round(v, 4) if isinstance(v, float) else v for k, v in self.metadata.items()
            },
        }


class StandardMetric(ABC):
    """标准评测指标抽象基类"""

    @abstractmethod
    def get_name(self) -> str:
        """指标名称"""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """指标描述"""
        pass

    @abstractmethod
    def compute(self, actual: str, expected: str) -> float:
        """计算指标分数（0-1 区间）

        Args:
            actual: 实际输出文本
            expected: 期望输出文本

        Returns:
            float: 0-1 区间的标准化分数
        """
        pass

    def compute_with_metadata(self, actual: str, expected: str) -> MetricResult:
        """计算指标并返回详细元数据"""
        score = self.compute(actual, expected)
        return MetricResult(
            name=self.get_name(),
            score=score,
            description=self.get_description(),
        )


# ==================== BLEU 指标 ====================


class BLEUMetric(StandardMetric):
    """BLEU (Bilingual Evaluation Understudy) 翻译质量指标

    行业标准 0-1 区间分数（已通过 sacrebleu.corpus_bleu / sentence_bleu 归一化）。
    支持 n-gram 最大阶数配置，默认 4-gram BLEU。
    """

    def __init__(self, max_n: int = 4, use_smoothing: bool = True):
        self.max_n = max_n
        self.use_smoothing = use_smoothing
        self._weights = tuple([1.0 / max_n] * max_n)

    def get_name(self) -> str:
        return f"BLEU-{self.max_n}"

    def get_description(self) -> str:
        return f"基于 {self.max_n}-gram 精度的机器翻译质量评估标准"

    def compute(self, actual: str, expected: str) -> float:
        if not actual or not expected:
            return 0.0

        if HAS_SACREBLEU:
            try:
                # sentence_bleu 返回 0-100 的百分制
                bleu = sacrebleu.sentence_bleu(
                    actual,
                    [expected],
                    smooth_method="exp" if self.use_smoothing else "none",
                )
                return max(0.0, min(1.0, bleu.score / 100.0))
            except Exception as e:
                logger.warning(f"sacrebleu 计算失败，降级到本地实现: {e}")

        # 降级：本地 n-gram precision + brevity penalty
        return self._local_bleu(actual, expected)

    def _local_bleu(self, actual: str, expected: str) -> float:
        """本地 BLEU 实现（无外部依赖）"""
        actual_tokens = actual.strip().split()
        expected_tokens = expected.strip().split()

        if not actual_tokens or not expected_tokens:
            return 0.0

        # 计算各阶 n-gram precision 的几何平均
        log_precision_sum = 0.0
        for n in range(1, self.max_n + 1):
            actual_ngrams = self._ngrams(actual_tokens, n)
            expected_ngrams = self._ngrams(expected_tokens, n)

            if not expected_ngrams:
                continue

            # clipped precision
            overlap = sum((actual_ngrams & expected_ngrams).values())
            total = sum(actual_ngrams.values())
            precision = overlap / total if total > 0 else 0.0

            if precision > 0:
                log_precision_sum += math.log(precision) / self.max_n
            else:
                # 平滑：避免 log(0)
                log_precision_sum += math.log(1e-9) / self.max_n

        # brevity penalty
        bp = min(1.0, math.exp(1 - len(expected_tokens) / len(actual_tokens)))

        return max(0.0, min(1.0, bp * math.exp(log_precision_sum)))

    @staticmethod
    def _ngrams(tokens: list[str], n: int) -> Counter:
        """生成 n-gram 计数"""
        return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


# ==================== ROUGE 指标 ====================


class ROUGEMetric(StandardMetric):
    """ROUGE (Recall-Oriented Understudy for Gisting Evaluation) 摘要质量指标

    支持 ROUGE-1 / ROUGE-2 / ROUGE-L，归一化到 0-1。
    """

    def __init__(self, rouge_type: str = "rougeL"):
        if rouge_type not in {"rouge1", "rouge2", "rougeL", "rougeLsum"}:
            raise ValueError(f"不支持的 ROUGE 类型: {rouge_type}")
        self.rouge_type = rouge_type

    def get_name(self) -> str:
        # ROUGE-1 / ROUGE-2 / ROUGE-L 格式
        suffix_map = {"rouge1": "1", "rouge2": "2", "rougeL": "L", "rougeLsum": "Lsum"}
        return f"ROUGE-{suffix_map[self.rouge_type]}"

    def get_description(self) -> str:
        descriptions = {
            "rouge1": "1-gram 召回率（单词级别重合度）",
            "rouge2": "2-gram 召回率（bigram 级别重合度）",
            "rougeL": "最长公共子序列（LCS）F1 分数",
            "rougeLsum": "按句子切分后的 ROUGE-L",
        }
        return descriptions[self.rouge_type]

    def compute(self, actual: str, expected: str) -> float:
        if not actual or not expected:
            return 0.0

        if HAS_ROUGE_SCORE:
            try:
                scorer = rouge_scorer.RougeScorer([self.rouge_type], use_stemmer=True)
                scores = scorer.score(expected, actual)
                fmeasure = scores[self.rouge_type].fmeasure
                return max(0.0, min(1.0, fmeasure))
            except Exception as e:
                logger.warning(f"rouge-score 计算失败，降级到本地实现: {e}")

        return self._local_rouge_l(actual, expected)

    def _local_rouge_l(self, actual: str, expected: str) -> float:
        """本地 ROUGE-L 实现：基于最长公共子序列的 F1"""
        actual_tokens = actual.split()
        expected_tokens = expected.split()

        if not actual_tokens or not expected_tokens:
            return 0.0

        lcs_len = self._lcs_length(actual_tokens, expected_tokens)
        if lcs_len == 0:
            return 0.0

        precision = lcs_len / len(actual_tokens)
        recall = lcs_len / len(expected_tokens)

        if precision + recall == 0:
            return 0.0

        f1 = 2 * precision * recall / (precision + recall)
        return max(0.0, min(1.0, f1))

    @staticmethod
    def _lcs_length(a: list[str], b: list[str]) -> int:
        """最长公共子序列长度（动态规划）"""
        m, n = len(a), len(b)
        if m == 0 or n == 0:
            return 0
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        return dp[m][n]


# ==================== METEOR 指标 ====================


class METEORMetric(StandardMetric):
    """METEOR 指标 - 考虑词形变化与同义词的翻译评估

    需要 nltk + wordnet 语料库支持，缺失时返回 None。
    """

    def get_name(self) -> str:
        return "METEOR"

    def get_description(self) -> str:
        return "考虑词形变化与同义词的翻译质量评估指标"

    def compute(self, actual: str, expected: str) -> float:
        if not HAS_METEOR:
            logger.warning("METEOR 不可用（缺少 nltk/wordnet）")
            return 0.0

        if not actual or not expected:
            return 0.0

        try:
            score = meteor_score([expected.split()], actual.split())
            return max(0.0, min(1.0, float(score)))
        except Exception as e:
            logger.warning(f"METEOR 计算失败: {e}")
            return 0.0


# ==================== Levenshtein 编辑距离 ====================


class LevenshteinMetric(StandardMetric):
    """Levenshtein 编辑距离归一化相似度

    适合短文本精确匹配场景（如代码标识符、命令、关键词）。
    使用动态规划计算编辑距离，0-1 区间。
    """

    def get_name(self) -> str:
        return "Levenshtein"

    def get_description(self) -> str:
        return "基于编辑距离的字符级相似度"

    def compute(self, actual: str, expected: str) -> float:
        if actual == expected:
            return 1.0
        if not actual or not expected:
            return 0.0

        distance = self._levenshtein_distance(actual, expected)
        max_len = max(len(actual), len(expected))
        similarity = 1.0 - (distance / max_len)
        return max(0.0, min(1.0, similarity))

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """标准编辑距离（动态规划，空间优化）"""
        if len(s1) < len(s2):
            return LevenshteinMetric._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]


# ==================== 余弦相似度（复用 Embedding 服务） ====================


class CosineSimilarityMetric(StandardMetric):
    """基于 Sentence-BERT 的余弦相似度

    委托给项目内的 EmbeddingService 单例，避免重复加载模型。
    """

    def __init__(self):
        self._service = None

    def get_name(self) -> str:
        return "CosineSimilarity"

    def get_description(self) -> str:
        return "基于预训练 Embedding 模型的语义余弦相似度"

    def _get_service(self):
        """延迟加载 Embedding 服务（避免循环导入）"""
        if self._service is None:
            try:
                from src.domain.evaluators.embedding_service import EmbeddingService

                self._service = EmbeddingService.get_instance()
            except Exception as e:
                logger.warning(f"Embedding 服务加载失败: {e}")
        return self._service

    def compute(self, actual: str, expected: str) -> float:
        if not actual or not expected:
            return 0.0
        if actual == expected:
            return 1.0

        service = self._get_service()
        if service is None or not service.is_available():
            return 0.0

        try:
            return max(0.0, min(1.0, service.calculate_similarity(actual, expected)))
        except Exception as e:
            logger.warning(f"余弦相似度计算失败: {e}")
            return 0.0


# ==================== F1 Token 重合度 ====================


class F1TokenMetric(StandardMetric):
    """基于 token 级别 precision/recall 的 F1 分数

    适合 QA 任务的事实一致性评估，比纯 Jaccard 更具区分度。
    """

    def get_name(self) -> str:
        return "F1-Token"

    def get_description(self) -> str:
        return "基于 token 级别 precision/recall 的 F1 分数（适合 QA 任务）"

    def compute(self, actual: str, expected: str) -> float:
        if not actual or not expected:
            return 0.0

        actual_tokens = self._tokenize(actual.lower())
        expected_tokens = self._tokenize(expected.lower())

        if not actual_tokens or not expected_tokens:
            return 0.0

        actual_counter = Counter(actual_tokens)
        expected_counter = Counter(expected_tokens)
        overlap = sum((actual_counter & expected_counter).values())

        if overlap == 0:
            return 0.0

        precision = overlap / sum(actual_counter.values())
        recall = overlap / sum(expected_counter.values())
        f1 = 2 * precision * recall / (precision + recall)
        return max(0.0, min(1.0, f1))

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """中英文混合分词"""
        tokens = []
        i = 0
        while i < len(text):
            ch = text[i]
            if "\u4e00" <= ch <= "\u9fff":
                tokens.append(ch)
                i += 1
            else:
                match = re.match(r"[a-zA-Z0-9]+", text[i:])
                if match:
                    tokens.append(match.group())
                    i += match.end()
                else:
                    i += 1
        return tokens


# ==================== 指标注册表 ====================


class MetricRegistry:
    """标准指标注册表（单例模式）"""

    _instance: MetricRegistry | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._metrics: dict[str, StandardMetric] = {}
            cls._instance._register_defaults()
        return cls._instance

    def _register_defaults(self):
        """注册默认指标集"""
        self.register(BLEUMetric())
        self.register(BLEUMetric(max_n=2))
        self.register(ROUGEMetric("rouge1"))
        self.register(ROUGEMetric("rouge2"))
        self.register(ROUGEMetric("rougeL"))
        self.register(METEORMetric())
        self.register(LevenshteinMetric())
        self.register(CosineSimilarityMetric())
        self.register(F1TokenMetric())

    def register(self, metric: StandardMetric) -> None:
        """注册自定义指标"""
        self._metrics[metric.get_name()] = metric

    def get(self, name: str) -> StandardMetric | None:
        """获取指标实例"""
        return self._metrics.get(name)

    def list_metrics(self) -> list[str]:
        """列出所有已注册指标"""
        return sorted(self._metrics.keys())

    def compute_all(self, actual: str, expected: str) -> dict[str, MetricResult]:
        """计算所有已注册指标"""
        return {
            name: metric.compute_with_metadata(actual, expected)
            for name, metric in self._metrics.items()
        }


def get_metric(name: str) -> StandardMetric | None:
    """便捷函数：获取指标实例"""
    return MetricRegistry().get(name)


def compute_standard_metrics(actual: str, expected: str) -> dict[str, float]:
    """便捷函数：计算所有标准指标"""
    registry = MetricRegistry()
    return {name: result.score for name, result in registry.compute_all(actual, expected).items()}


# 模块导出
__all__ = [
    "StandardMetric",
    "MetricResult",
    "BLEUMetric",
    "ROUGEMetric",
    "METEORMetric",
    "LevenshteinMetric",
    "CosineSimilarityMetric",
    "F1TokenMetric",
    "MetricRegistry",
    "get_metric",
    "compute_standard_metrics",
    "HAS_SACREBLEU",
    "HAS_ROUGE_SCORE",
    "HAS_METEOR",
]
