"""
评估器单元测试公共配置
提供 EmbeddingService mock，避免测试时下载模型
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_embedding_service():
    """
    Mock EmbeddingService，避免测试时下载和加载模型
    """
    with patch("src.domain.evaluators.embedding_service.EmbeddingService") as MockEmbeddingService:
        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.calculate_similarity.return_value = 0.8
        mock_instance.calculate_similarity_async.return_value = 0.8
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
