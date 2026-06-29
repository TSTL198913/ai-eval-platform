"""
黄金数据集单元测试
测试目标：验证 GoldenDatasetManager 的数据集管理、样本校正、few-shot 生成
关键发现：
- 数据集支持创建、添加样本、校正样本
- 样本校正是合并而非覆盖，避免数据丢失
- Few-shot 示例按更新时间倒序排列
- 支持多维度评分和元数据
"""

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.golden_dataset import (
    GoldenDataset,
    GoldenDatasetManager,
    GoldenSample,
)


class TestGoldenSample:
    """GoldenSample 数据类测试"""

    def test_sample_creation_minimal(self):
        """最小化样本创建应正常"""
        sample = GoldenSample(
            id="s001",
            user_input="What is AI?",
            actual_output="Artificial Intelligence",
        )
        assert sample.id == "s001"
        assert sample.user_input == "What is AI?"
        assert sample.actual_output == "Artificial Intelligence"
        assert sample.expected_output is None
        assert sample.dimensions == ["correctness"]
        assert sample.scores == {}
        assert sample.human_corrected is False
        assert sample.corrected_by is None

    def test_sample_creation_full(self):
        """完整样本创建应正常"""
        sample = GoldenSample(
            id="s002",
            user_input="What is ML?",
            actual_output="Machine Learning",
            expected_output="A subset of AI",
            dimensions=["correctness", "completeness"],
            scores={"correctness": 85.0, "completeness": 70.0},
            human_corrected=True,
            corrected_by="expert1",
        )
        assert sample.expected_output == "A subset of AI"
        assert sample.dimensions == ["correctness", "completeness"]
        assert sample.scores["correctness"] == 85.0
        assert sample.human_corrected is True
        assert sample.corrected_by == "expert1"

    def test_to_dict_returns_all_fields(self):
        """to_dict 应返回所有字段"""
        sample = GoldenSample(
            id="s003",
            user_input="test",
            actual_output="output",
            scores={"correctness": 90.0},
        )
        d = sample.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "s003"
        assert d["user_input"] == "test"
        assert d["actual_output"] == "output"
        assert d["scores"] == {"correctness": 90.0}
        assert "created_at" in d
        assert "updated_at" in d

    def test_to_few_shot_example_with_scores(self):
        """带评分的 few-shot 示例生成应正确"""
        sample = GoldenSample(
            id="s004",
            user_input="What is AI?",
            actual_output="Artificial Intelligence",
            scores={"correctness": 95.0, "completeness": 88.0},
        )
        example = sample.to_few_shot_example()
        assert "What is AI?" in example
        assert "Artificial Intelligence" in example
        assert "correctness: 95.0/100" in example
        assert "completeness: 88.0/100" in example
        assert "示例开始" in example
        assert "示例结束" in example

    def test_to_few_shot_example_with_expected(self):
        """带期望输出的 few-shot 示例应包含期望输出"""
        sample = GoldenSample(
            id="s005",
            user_input="Hi",
            actual_output="Hello there",
            expected_output="Hello! How can I help?",
            scores={"correctness": 90.0},
        )
        example = sample.to_few_shot_example()
        assert "期望输出" in example
        assert "Hello! How can I help?" in example

    def test_to_few_shot_example_without_expected(self):
        """无期望输出时不应包含期望输出字段"""
        sample = GoldenSample(
            id="s006",
            user_input="Hi",
            actual_output="Hello",
            scores={"correctness": 90.0},
        )
        example = sample.to_few_shot_example()
        assert "期望输出" not in example


class TestGoldenDataset:
    """GoldenDataset 数据类测试"""

    def test_dataset_creation(self):
        """数据集创建应正常"""
        dataset = GoldenDataset(
            id="d001",
            name="Test Dataset",
            description="Test description",
            category="general",
        )
        assert dataset.id == "d001"
        assert dataset.name == "Test Dataset"
        assert dataset.description == "Test description"
        assert dataset.category == "general"
        assert dataset.samples == []

    def test_corrected_count_zero(self):
        """无校正样本时 corrected_count 应为 0"""
        dataset = GoldenDataset(
            id="d002",
            name="Test",
            description="",
            category="general",
            samples=[
                GoldenSample(id="s1", user_input="q1", actual_output="a1"),
                GoldenSample(id="s2", user_input="q2", actual_output="a2"),
            ],
        )
        assert dataset.corrected_count == 0

    def test_corrected_count_with_corrected(self):
        """有校正样本时 corrected_count 应正确统计"""
        dataset = GoldenDataset(
            id="d003",
            name="Test",
            description="",
            category="general",
            samples=[
                GoldenSample(id="s1", user_input="q1", actual_output="a1"),
                GoldenSample(
                    id="s2",
                    user_input="q2",
                    actual_output="a2",
                    human_corrected=True,
                    corrected_by="expert",
                ),
                GoldenSample(
                    id="s3",
                    user_input="q3",
                    actual_output="a3",
                    human_corrected=True,
                    corrected_by="expert",
                ),
            ],
        )
        assert dataset.corrected_count == 2


class TestGoldenDatasetManagerPositive:
    """正向测试 - 数据集管理正常操作"""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def manager(self, temp_dir):
        return GoldenDatasetManager(data_dir=temp_dir)

    def test_create_dataset(self, manager):
        """创建数据集应成功"""
        dataset = manager.create_dataset(
            name="Customer Service",
            description="客服对话黄金标准",
            category="correctness",
        )
        assert dataset.id is not None
        assert len(dataset.id) == 8
        assert dataset.name == "Customer Service"
        assert dataset.category == "correctness"
        assert dataset.samples == []

    def test_add_sample(self, manager):
        """添加样本应成功"""
        dataset = manager.create_dataset(name="Test")
        sample = manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "s001",
                "user_input": "What is AI?",
                "actual_output": "Artificial Intelligence",
                "scores": {"correctness": 90.0},
            },
        )
        assert sample is not None
        assert sample.id == "s001"
        assert sample.user_input == "What is AI?"
        assert len(dataset.samples) == 1
        assert dataset.samples[0].id == "s001"

    def test_add_sample_with_custom_id(self, manager):
        """自定义样本ID应正常"""
        dataset = manager.create_dataset(name="Test")
        sample = manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "custom-id-123",
                "user_input": "test",
                "actual_output": "output",
            },
        )
        assert sample.id == "custom-id-123"

    def test_correct_sample_merges_scores(self, manager):
        """校正样本应合并分数而非覆盖"""
        dataset = manager.create_dataset(name="Test")
        manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "s001",
                "user_input": "test",
                "actual_output": "output",
                "scores": {"correctness": 80.0, "completeness": 70.0},
            },
        )

        # 只校正 correctness 维度
        corrected = manager.correct_sample(
            sample_id="s001",
            corrected_scores={"correctness": 95.0},
            corrected_by="expert1",
        )

        assert corrected is not None
        assert corrected.human_corrected is True
        assert corrected.corrected_by == "expert1"
        assert corrected.corrected_at is not None
        # 合并而非覆盖：completeness 应保留
        assert corrected.scores["correctness"] == 95.0
        assert corrected.scores["completeness"] == 70.0

    def test_correct_sample_adds_new_dimension(self, manager):
        """校正时添加新维度应正常"""
        dataset = manager.create_dataset(name="Test")
        manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "s002",
                "user_input": "test",
                "actual_output": "output",
                "scores": {"correctness": 80.0},
            },
        )

        corrected = manager.correct_sample(
            sample_id="s002",
            corrected_scores={"safety": 90.0},  # 新维度
            corrected_by="expert1",
        )

        assert "safety" in corrected.scores
        assert corrected.scores["safety"] == 90.0
        assert corrected.scores["correctness"] == 80.0  # 保留原有

    def test_get_few_shot_examples(self, manager):
        """获取 few-shot 示例应返回最近校正的样本"""
        dataset = manager.create_dataset(name="Test")

        # 添加2个校正样本和1个未校正样本
        manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "s1",
                "user_input": "q1",
                "actual_output": "a1",
                "scores": {"correctness": 90.0},
            },
        )
        manager.correct_sample("s1", {"correctness": 95.0}, "expert")

        manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "s2",
                "user_input": "q2",
                "actual_output": "a2",
                "scores": {"correctness": 80.0},
            },
        )
        manager.correct_sample("s2", {"correctness": 85.0}, "expert")

        manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "s3",
                "user_input": "q3",
                "actual_output": "a3",
                "scores": {"correctness": 70.0},
            },
        )  # 未校正

        examples = manager.get_few_shot_examples(dataset.id, limit=5)

        # 只返回校正过的样本
        assert len(examples) == 2
        # 都是字符串
        assert all(isinstance(e, str) for e in examples)

    def test_get_few_shot_examples_limit(self, manager):
        """few-shot 示例数量应受 limit 限制"""
        dataset = manager.create_dataset(name="Test")

        for i in range(10):
            sid = f"s{i}"
            manager.add_sample(
                dataset_id=dataset.id,
                sample_data={
                    "id": sid,
                    "user_input": f"q{i}",
                    "actual_output": f"a{i}",
                    "scores": {"correctness": float(i * 10)},
                },
            )
            manager.correct_sample(sid, {"correctness": 95.0}, "expert")

        examples = manager.get_few_shot_examples(dataset.id, limit=3)
        assert len(examples) == 3

    def test_get_dataset(self, manager):
        """获取数据集应正常"""
        dataset = manager.create_dataset(name="Test Dataset")
        retrieved = manager.get_dataset(dataset.id)
        assert retrieved is not None
        assert retrieved.id == dataset.id
        assert retrieved.name == "Test Dataset"

    def test_list_datasets(self, manager):
        """列出数据集应正常"""
        assert len(manager.list_datasets()) == 0

        manager.create_dataset(name="Dataset 1")
        manager.create_dataset(name="Dataset 2")

        assert len(manager.list_datasets()) == 2


class TestGoldenDatasetManagerNegative:
    """负向测试 - 错误场景处理"""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def manager(self, temp_dir):
        return GoldenDatasetManager(data_dir=temp_dir)

    def test_add_sample_to_nonexistent_dataset(self, manager):
        """向不存在的数据集添加样本应返回 None"""
        sample = manager.add_sample(
            dataset_id="nonexistent",
            sample_data={"user_input": "test", "actual_output": "output"},
        )
        assert sample is None

    def test_correct_nonexistent_sample(self, manager):
        """校正不存在的样本应返回 None"""
        result = manager.correct_sample(
            sample_id="nonexistent",
            corrected_scores={"correctness": 90.0},
            corrected_by="expert",
        )
        assert result is None

    def test_get_nonexistent_dataset(self, manager):
        """获取不存在的数据集应返回 None"""
        assert manager.get_dataset("nonexistent") is None

    def test_few_shot_empty_dataset(self, manager):
        """空数据集的 few-shot 示例应返回空列表"""
        dataset = manager.create_dataset(name="Empty")
        examples = manager.get_few_shot_examples(dataset.id)
        assert examples == []

    def test_few_shot_no_corrected_samples(self, manager):
        """没有校正样本时 few-shot 应返回空列表"""
        dataset = manager.create_dataset(name="Test")
        manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "s1",
                "user_input": "test",
                "actual_output": "output",
            },
        )
        # 未校正
        examples = manager.get_few_shot_examples(dataset.id)
        assert examples == []


class TestGoldenDatasetManagerBoundary:
    """边界测试"""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def manager(self, temp_dir):
        return GoldenDatasetManager(data_dir=temp_dir)

    def test_empty_scores_correction(self, manager):
        """空字典校正应正常（不改变任何分数，但标记为已校正）"""
        dataset = manager.create_dataset(name="Test")
        manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "s001",
                "user_input": "test",
                "actual_output": "output",
                "scores": {"correctness": 80.0},
            },
        )

        corrected = manager.correct_sample(
            sample_id="s001",
            corrected_scores={},  # 空字典
            corrected_by="expert",
        )

        assert corrected.human_corrected is True
        assert corrected.scores["correctness"] == 80.0  # 保持不变

    def test_many_samples(self, manager):
        """大量样本应正常工作"""
        dataset = manager.create_dataset(name="Large Dataset")
        for i in range(100):
            manager.add_sample(
                dataset_id=dataset.id,
                sample_data={
                    "id": f"s{i}",
                    "user_input": f"question_{i}",
                    "actual_output": f"answer_{i}",
                    "scores": {"correctness": float(i)},
                },
            )

        assert len(dataset.samples) == 100
        assert dataset.samples[99].id == "s99"

    def test_special_characters_in_input(self, manager):
        """特殊字符输入应正常处理"""
        dataset = manager.create_dataset(name="Test")
        sample = manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "special",
                "user_input": "<script>alert('XSS')</script>",
                "actual_output": '{"key": "value"}',
                "scores": {"safety": 100.0},
            },
        )
        assert sample.user_input == "<script>alert('XSS')</script>"
        assert sample.actual_output == '{"key": "value"}'

    def test_long_text_input(self, manager):
        """长文本输入应正常处理"""
        long_text = "x" * 10000
        dataset = manager.create_dataset(name="Test")
        sample = manager.add_sample(
            dataset_id=dataset.id,
            sample_data={
                "id": "long",
                "user_input": long_text,
                "actual_output": long_text,
                "scores": {"correctness": 90.0},
            },
        )
        assert len(sample.user_input) == 10000
        assert len(sample.actual_output) == 10000
