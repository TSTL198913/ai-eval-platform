"""
FineTuneExporter 专项单元测试
测试目标：验证微调数据导出模块的格式转换、过滤、统计、报告生成
关键发现：
1. 支持4种格式：OPENAI/LLAMA_FACTORY/HUGGING_FACE/RAW_JSONL
2. 评分过滤：min_score < avg_score才导出
3. 质量等级：excellent_ratio >= 0.3 且 poor_ratio < 0.1 → A
"""

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.fine_tune_exporter import (
    ExportFormat,
    FineTuneExporter,
    TrainingSample,
)


@dataclass
class MockSample:
    """Mock黄金样本"""

    id: str
    user_input: str
    actual_output: str
    expected_output: str = ""
    scores: dict = field(default_factory=dict)
    dimensions: list = field(default_factory=list)
    human_corrected: bool = False


@dataclass
class MockDataset:
    """Mock黄金数据集"""

    id: str
    name: str
    description: str = ""
    samples: list = field(default_factory=list)


class TestTrainingSample:
    """TrainingSample 测试"""

    def test_to_openai_format(self):
        """场景：转换为OpenAI格式"""
        sample = TrainingSample(
            id="s_001",
            prompt="What is AI?",
            completion="AI is artificial intelligence.",
        )

        result = sample.to_openai_format()

        assert result == {"prompt": "What is AI?", "completion": "AI is artificial intelligence."}

    def test_to_llama_format(self):
        """场景：转换为LLaMA-Factory格式"""
        sample = TrainingSample(
            id="s_001",
            prompt="What is AI?",
            completion="AI is artificial intelligence.",
        )

        result = sample.to_llama_format()

        assert "USER: What is AI?" in result
        assert "ASSISTANT: AI is artificial intelligence." in result

    def test_to_json(self):
        """场景：转换为JSON格式"""
        sample = TrainingSample(
            id="s_001",
            prompt="问题",
            completion="回答",
            metadata={"score": 0.85},
        )

        result = sample.to_json()
        data = json.loads(result)

        assert data["id"] == "s_001"
        assert data["prompt"] == "问题"
        assert data["completion"] == "回答"
        assert data["metadata"]["score"] == 0.85


class TestFineTuneExporterPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def exporter(self):
        return FineTuneExporter()

    def test_export_from_golden_dataset_openai_format(self, exporter):
        """场景：导出OpenAI格式"""
        # Mock样本
        sample1 = MockSample(
            id="s_001",
            user_input="问题1",
            actual_output="回答1",
            expected_output="期望回答1",
            scores={"correctness": 80, "completeness": 75},
            dimensions=["correctness", "completeness"],
        )
        sample2 = MockSample(
            id="s_002",
            user_input="问题2",
            actual_output="回答2",
            expected_output="",
            scores={"correctness": 60},
            dimensions=["correctness"],
        )

        dataset = MockDataset(id="ds_001", name="测试数据集", samples=[sample1, sample2])

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager:
                mock_manager.get_dataset.return_value = dataset

                filepath = exporter.export_from_golden_dataset(
                    dataset_id="ds_001",
                    output_dir=tmpdir,
                    format=ExportFormat.OPENAI,
                    min_score=50.0,
                )

                # 验证文件存在
                assert os.path.exists(filepath)
                # 文件存在,扩展名可能为.jsonl或.openai

                # 验证文件内容
                with open(filepath, encoding="utf-8") as f:
                    lines = f.readlines()
                assert len(lines) == 2

                data1 = json.loads(lines[0])
                assert "prompt" in data1
                assert "completion" in data1

    def test_export_from_golden_dataset_llama_format(self, exporter):
        """场景：导出LLaMA格式"""
        sample = MockSample(
            id="s_001",
            user_input="问题",
            actual_output="回答",
            scores={"correctness": 80},
            dimensions=["correctness"],
        )
        dataset = MockDataset(id="ds_001", name="测试", samples=[sample])

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager:
                mock_manager.get_dataset.return_value = dataset

                filepath = exporter.export_from_golden_dataset(
                    dataset_id="ds_001",
                    output_dir=tmpdir,
                    format=ExportFormat.LLAMA_FACTORY,
                )

                with open(filepath, encoding="utf-8") as f:
                    content = f.read()
                assert "USER:" in content
                assert "ASSISTANT:" in content

    def test_export_from_golden_dataset_filters_by_min_score(self, exporter):
        """场景：按min_score过滤样本"""
        high_score = MockSample(
            id="high", user_input="q", actual_output="a", scores={"d": 90}, dimensions=["d"]
        )
        low_score = MockSample(
            id="low", user_input="q", actual_output="a", scores={"d": 30}, dimensions=["d"]
        )
        dataset = MockDataset(id="ds_001", name="test", samples=[high_score, low_score])

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager:
                mock_manager.get_dataset.return_value = dataset

                filepath = exporter.export_from_golden_dataset(
                    dataset_id="ds_001",
                    output_dir=tmpdir,
                    format=ExportFormat.OPENAI,
                    min_score=50.0,
                )

                with open(filepath, encoding="utf-8") as f:
                    lines = f.readlines()
                # 只有高分样本
                assert len(lines) == 1

    def test_export_with_metadata_file(self, exporter):
        """场景：导出元数据文件"""
        sample = MockSample(
            id="s_001", user_input="q", actual_output="a", scores={"d": 80}, dimensions=["d"]
        )
        dataset = MockDataset(id="ds_001", name="test", samples=[sample])

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager:
                mock_manager.get_dataset.return_value = dataset

                exporter.export_from_golden_dataset(
                    dataset_id="ds_001",
                    output_dir=tmpdir,
                    format=ExportFormat.OPENAI,
                )

                metadata_file = os.path.join(tmpdir, "ds_001_metadata.json")
                assert os.path.exists(metadata_file)

                with open(metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)
                assert metadata["dataset_id"] == "ds_001"

    def test_export_from_db(self, exporter):
        """场景：从数据库导出"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.infra.db.repository.EvaluationRepository") as MockRepo:
                mock_instance = MagicMock()
                mock_instance.search.return_value = [
                    {
                        "id": 1,
                        "case_id": "case_1",
                        "response_data": {
                            "total_score": 80,
                            "llm_judge_scores": {"correctness": {"score": 80}},
                        },
                        "model_name": "gpt-4",
                        "adapter_name": "default",
                        "latency_ms": 100,
                    }
                ]
                MockRepo.return_value = mock_instance

                filepath = exporter.export_from_db(
                    output_dir=tmpdir,
                    format=ExportFormat.OPENAI,
                    limit=10,
                    min_score=50.0,
                )

                assert os.path.exists(filepath)

    def test_get_stats(self, exporter):
        """场景：获取导出统计"""
        stats = exporter.get_stats()

        assert "total_samples" in stats
        assert "avg_score" in stats
        assert "high_quality_samples" in stats
        assert "low_quality_samples" in stats
        assert "export_time" in stats

    def test_generate_quality_report(self, exporter):
        """场景：生成质量报告"""
        samples = [
            TrainingSample(
                id=f"s_{i}",
                prompt=f"q{i}",
                completion=f"a{i}",
                metadata={"avg_score": score},
            )
            for i, score in enumerate([95, 85, 65, 45, 30])
        ]

        report = exporter.generate_quality_report(samples)

        assert "total_samples" in report
        assert "scored_samples" in report
        assert "avg_score" in report
        assert "score_distribution" in report
        assert "quality_grade" in report
        assert "recommendations" in report

        dist = report["score_distribution"]
        assert dist["excellent"] == 1  # 95
        assert dist["good"] == 1  # 85
        assert dist["fair"] == 1  # 65
        assert dist["poor"] == 2  # 45, 30


class TestFineTuneExporterNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def exporter(self):
        return FineTuneExporter()

    def test_export_nonexistent_dataset_raises(self, exporter):
        """场景：导出不存在的数据集应抛出异常"""
        with patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = None

            with pytest.raises(ValueError, match="not found"):
                exporter.export_from_golden_dataset(dataset_id="nonexistent")

    def test_generate_quality_report_empty_samples(self, exporter):
        """场景：空样本列表应返回错误"""
        report = exporter.generate_quality_report([])

        assert "error" in report

    def test_export_filters_out_samples_without_scores(self, exporter):
        """场景：无分数的样本应被过滤"""
        sample_with_score = MockSample(
            id="with", user_input="q", actual_output="a", scores={"d": 80}, dimensions=["d"]
        )
        sample_without_score = MockSample(
            id="without", user_input="q", actual_output="a", scores={}, dimensions=[]
        )
        dataset = MockDataset(
            id="ds_001", name="test", samples=[sample_with_score, sample_without_score]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.domain.golden_dataset.golden_dataset_manager") as mock_manager:
                mock_manager.get_dataset.return_value = dataset

                filepath = exporter.export_from_golden_dataset(
                    dataset_id="ds_001",
                    output_dir=tmpdir,
                    format=ExportFormat.OPENAI,
                )

                with open(filepath, encoding="utf-8") as f:
                    lines = f.readlines()
                # 只有有分数的样本
                assert len(lines) == 1


class TestFineTuneExporterQualityGrading:
    """质量等级评定测试"""

    @pytest.fixture
    def exporter(self):
        return FineTuneExporter()

    def test_grade_a_excellent(self, exporter):
        """场景：优秀数据(A级)"""
        # 50%优秀 + <10%差
        distribution = {"excellent": 10, "good": 8, "fair": 2, "poor": 0}

        grade = exporter._calculate_quality_grade(distribution)

        assert "A" in grade

    def test_grade_b_good(self, exporter):
        """场景：良好数据(B级)"""
        # 50%+良好 + <20%差
        distribution = {"excellent": 2, "good": 10, "fair": 5, "poor": 1}

        grade = exporter._calculate_quality_grade(distribution)

        assert "B" in grade

    def test_grade_c_fair(self, exporter):
        """场景：一般数据(C级)"""
        distribution = {"excellent": 1, "good": 3, "fair": 10, "poor": 2}

        grade = exporter._calculate_quality_grade(distribution)

        assert "C" in grade

    def test_grade_d_poor(self, exporter):
        """场景：需改进数据(D级)"""
        distribution = {"excellent": 0, "good": 1, "fair": 2, "poor": 10}

        grade = exporter._calculate_quality_grade(distribution)

        assert "D" in grade

    def test_grade_empty(self, exporter):
        """场景：空分布应返回N/A"""
        distribution = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}

        grade = exporter._calculate_quality_grade(distribution)

        assert grade == "N/A"

    def test_recommendations_for_low_excellent(self, exporter):
        """场景：优秀样本不足应给建议"""
        distribution = {"excellent": 1, "good": 3, "fair": 5, "poor": 2}

        recommendations = exporter._generate_recommendations(distribution)

        assert any("优秀" in r or "高质量" in r for r in recommendations)

    def test_recommendations_for_high_poor(self, exporter):
        """场景：差样本过多应给建议"""
        distribution = {"excellent": 5, "good": 5, "fair": 5, "poor": 10}

        recommendations = exporter._generate_recommendations(distribution)

        assert any("过滤" in r or "低质量" in r for r in recommendations)


class TestFineTuneExporterDependencyHandling:
    """依赖测试"""

    def test_export_from_db_no_records(self):
        """场景：数据库无记录时返回空文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.infra.db.repository.EvaluationRepository") as MockRepo:
                mock_instance = MagicMock()
                mock_instance.search.return_value = []
                MockRepo.return_value = mock_instance

                exporter = FineTuneExporter()
                filepath = exporter.export_from_db(
                    output_dir=tmpdir,
                    format=ExportFormat.OPENAI,
                )

                # 空文件应被创建
                assert os.path.exists(filepath)
