"""
评估器单元测试公共配置
提供 EmbeddingService mock，避免测试时下载模型
"""

import difflib
from unittest.mock import MagicMock, patch

import pytest


def _calculate_dynamic_similarity(text1: str, text2: str) -> float:
    """
    根据输入文本动态计算语义相似度
    将字符级别的相似度映射到语义级别的相似度
    - 完全相同：1.0
    - 高度相似（ratio > 0.6）：0.75-1.0
    - 部分相似（ratio > 0.3）：0.4-0.75
    - 低相似（ratio > 0.1）：0.1-0.4
    - 几乎不相似：0.0-0.1
    """
    if not text1 or not text2:
        return 0.5

    if text1 == text2:
        return 1.0

    ratio = difflib.SequenceMatcher(None, text1, text2).ratio()

    if ratio == 0.0:
        return 0.0
    elif ratio > 0.8:
        return min(1.0, ratio * 0.95 + 0.05)
    elif ratio > 0.6:
        return 0.75 + (ratio - 0.6) * 0.625
    elif ratio > 0.4:
        return 0.5 + (ratio - 0.4) * 0.625
    elif ratio > 0.2:
        return 0.2 + (ratio - 0.2) * 0.5
    elif ratio > 0.05:
        return ratio * 0.5
    else:
        return ratio


@pytest.fixture(autouse=True)
def mock_embedding_service():
    """
    Mock EmbeddingService，避免测试时下载和加载模型
    动态返回相似度分数，使测试更加真实
    """
    with patch("src.domain.evaluators.embedding_service.EmbeddingService") as MockEmbeddingService:
        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.calculate_similarity.side_effect = _calculate_dynamic_similarity
        mock_instance.calculate_similarity_async.side_effect = _calculate_dynamic_similarity
        MockEmbeddingService.get_instance.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_sentence_transformer():
    """
    Mock SentenceTransformer，防止模型加载
    """
    with patch("sentence_transformers.SentenceTransformer") as MockST:
        mock_model = MagicMock()
        MockST.return_value = mock_model
        yield mock_model
