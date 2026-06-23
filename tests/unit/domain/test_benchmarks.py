"""
Benchmarks模块专项测试
测试目标：验证基准测试框架的核心功能
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.benchmarks.base import BenchmarkResult
from src.domain.benchmarks.dataset_loader import DatasetLoader
from src.domain.benchmarks.registry import BenchmarkRegistry


class TestBenchmarkResult:
    """BenchmarkResult数据类测试"""

    def test_result_construction(self):
        """应能正确构造BenchmarkResult"""
        result = BenchmarkResult(
            benchmark_name="test_benchmark",
            total_samples=100,
            correct_samples=80,
            accuracy=0.8,
        )

        assert result.benchmark_name == "test_benchmark"
        assert result.total_samples == 100
        assert result.correct_samples == 80
        assert result.accuracy == 0.8
        assert result.scores == []
        assert result.metadata == {}
        assert result.error_count == 0
        assert result.error_messages == []

    def test_result_with_optional_fields(self):
        """应能正确设置可选字段"""
        scores = [{"sample_id": 1, "correct": True}]
        metadata = {"model": "test_model"}
        error_messages = ["error 1", "error 2"]

        result = BenchmarkResult(
            benchmark_name="test",
            total_samples=10,
            correct_samples=5,
            accuracy=0.5,
            scores=scores,
            metadata=metadata,
            error_count=2,
            error_messages=error_messages,
        )

        assert result.scores == scores
        assert result.metadata == metadata
        assert result.error_count == 2
        assert result.error_messages == error_messages

    def test_to_dict(self):
        """to_dict应返回正确的字典表示"""
        result = BenchmarkResult(
            benchmark_name="test",
            total_samples=100,
            correct_samples=80,
            accuracy=0.8,
            scores=[{"id": 1}],
            metadata={"key": "value"},
            error_count=1,
            error_messages=["test error"],
        )

        result_dict = result.to_dict()

        assert result_dict["benchmark_name"] == "test"
        assert result_dict["total_samples"] == 100
        assert result_dict["correct_samples"] == 80
        assert result_dict["accuracy"] == 0.8
        assert result_dict["scores"] == [{"id": 1}]
        assert result_dict["metadata"] == {"key": "value"}
        assert result_dict["error_count"] == 1
        assert result_dict["error_messages"] == ["test error"]


class TestBenchmarkRegistry:
    """BenchmarkRegistry注册中心测试"""

    def test_register_and_get(self):
        """注册和获取基准测试类"""

        @BenchmarkRegistry.register("test_benchmark")
        class TestBenchmark:
            name = "test_benchmark"
            description = "Test benchmark"
            category = "test"
            num_samples = 10

        benchmark_class = BenchmarkRegistry.get("test_benchmark")
        assert benchmark_class == TestBenchmark

    def test_get_unknown_benchmark(self):
        """获取未知基准测试应抛出异常"""
        with pytest.raises(ValueError, match="Unknown benchmark"):
            BenchmarkRegistry.get("unknown")

    def test_list_benchmarks(self):
        """列出所有注册的基准测试"""
        benchmarks = BenchmarkRegistry.list()
        assert isinstance(benchmarks, list)

    def test_get_info(self):
        """获取基准测试信息"""

        @BenchmarkRegistry.register("info_test")
        class InfoTestBenchmark:
            name = "info_test"
            description = "Info test"
            category = "test"
            num_samples = 20

        info = BenchmarkRegistry.get_info("info_test")
        assert info["name"] == "info_test"
        assert info["description"] == "Info test"
        assert info["category"] == "test"
        assert info["num_samples"] == 20


class TestDatasetLoader:
    """DatasetLoader数据集加载器测试"""

    def test_load_jsonl_file_not_exists(self):
        """加载不存在的文件应返回空列表"""
        samples = DatasetLoader.load_jsonl("non_existent.jsonl")
        assert samples == []

    def test_load_jsonl_invalid_json(self):
        """加载包含无效JSON的文件应跳过错误行"""
        with patch("src.domain.benchmarks.dataset_loader.Path.exists", return_value=True):
            with patch("builtins.open", MagicMock()):
                mock_file = MagicMock()
                mock_file.__enter__.return_value = mock_file
                mock_file.__iter__.return_value = iter(["invalid json", '{"valid": "data"}'])
                with patch("builtins.open", return_value=mock_file):
                    samples = DatasetLoader.load_jsonl("test.jsonl")
                    assert len(samples) == 1
                    assert samples[0] == {"valid": "data"}

    def test_load_mmlu(self):
        """加载MMLU数据集"""
        samples = DatasetLoader.load_mmlu()
        assert isinstance(samples, list)

    def test_load_mmlu_with_subject(self):
        """按学科过滤加载MMLU数据集"""
        samples = DatasetLoader.load_mmlu(subject="mathematics")
        assert isinstance(samples, list)

    def test_load_mmlu_with_limit(self):
        """限制MMLU数据集样本数量"""
        samples = DatasetLoader.load_mmlu(limit=5)
        assert isinstance(samples, list)
        assert len(samples) <= 5

    def test_load_gsm8k(self):
        """加载GSM8K数据集"""
        samples = DatasetLoader.load_gsm8k()
        assert isinstance(samples, list)

    def test_load_gsm8k_with_limit(self):
        """限制GSM8K数据集样本数量"""
        samples = DatasetLoader.load_gsm8k(limit=5)
        assert isinstance(samples, list)
        assert len(samples) <= 5

    def test_load_humaneval(self):
        """加载HumanEval数据集"""
        samples = DatasetLoader.load_humaneval()
        assert isinstance(samples, list)

    def test_load_humaneval_with_limit(self):
        """限制HumanEval数据集样本数量"""
        samples = DatasetLoader.load_humaneval(limit=5)
        assert isinstance(samples, list)
        assert len(samples) <= 5

    def test_get_dataset_info(self):
        """获取数据集信息"""
        info = DatasetLoader.get_dataset_info()
        assert isinstance(info, dict)
        assert "mmlu" in info
        assert "gsm8k" in info
        assert "humaneval" in info

    def test_is_real_dataset_available(self):
        """检查真实数据集可用性"""
        assert DatasetLoader.is_real_dataset_available("mmlu") is True
        assert DatasetLoader.is_real_dataset_available("gsm8k") is True
        assert DatasetLoader.is_real_dataset_available("humaneval") is True
        assert DatasetLoader.is_real_dataset_available("unknown") is False
