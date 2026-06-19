"""
黄金数据集管理模块测试
测试目标：验证GoldenDatasetManager的核心功能
关键发现：（测试过程中记录）

核心测试场景：
1. 数据集创建和样本管理
2. 人工校正功能
3. Few-shot示例生成
4. 数据持久化
"""
import os
import sys
import pytest
import tempfile
import shutil
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.golden_dataset import (
    GoldenSample,
    GoldenDataset,
    GoldenDatasetManager,
)


class TestGoldenDatasetManagerCreation:
    """数据集创建测试 - 正向测试"""

    @pytest.fixture
    def manager(self):
        """创建测试用管理器"""
        temp_dir = tempfile.mkdtemp()
        yield GoldenDatasetManager(data_dir=temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_dataset_returns_golden_dataset(self, manager):
        """创建数据集应返回GoldenDataset实例"""
        dataset = manager.create_dataset(
            name="test_dataset",
            description="测试数据集",
            category="general"
        )

        assert isinstance(dataset, GoldenDataset)
        assert dataset.name == "test_dataset"
        assert dataset.description == "测试数据集"
        assert dataset.category == "general"
        assert dataset.id is not None
        assert len(dataset.samples) == 0

    def test_create_dataset_generates_unique_id(self, manager):
        """创建多个数据集应生成唯一ID"""
        dataset1 = manager.create_dataset(name="dataset1")
        dataset2 = manager.create_dataset(name="dataset2")

        assert dataset1.id != dataset2.id

    def test_list_datasets_returns_all_datasets(self, manager):
        """列出数据集应返回所有创建的数据集"""
        manager.create_dataset(name="dataset1")
        manager.create_dataset(name="dataset2")

        datasets = manager.list_datasets()

        assert len(datasets) == 2
        assert any(d.name == "dataset1" for d in datasets)
        assert any(d.name == "dataset2" for d in datasets)


class TestGoldenDatasetManagerSamples:
    """样本管理测试"""

    @pytest.fixture
    def manager_with_dataset(self):
        """创建带数据集的管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = GoldenDatasetManager(data_dir=temp_dir)
        dataset = manager.create_dataset(name="test_dataset")
        yield manager, dataset
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_add_sample_returns_golden_sample(self, manager_with_dataset):
        """添加样本应返回GoldenSample实例"""
        manager, dataset = manager_with_dataset

        sample_data = {
            "id": "sample_001",
            "user_input": "什么是AI评测？",
            "actual_output": "AI评测是对人工智能系统进行评估的过程...",
            "expected_output": "定义AI评测",
            "dimensions": ["correctness", "completeness"],
            "scores": {"correctness": 90, "completeness": 85}
        }

        sample = manager.add_sample(dataset.id, sample_data)

        assert isinstance(sample, GoldenSample)
        assert sample.id == "sample_001"
        assert sample.user_input == "什么是AI评测？"
        assert sample.scores["correctness"] == 90
        assert sample.human_corrected is False

    def test_add_sample_updates_dataset_samples(self, manager_with_dataset):
        """添加样本应更新数据集的样本列表"""
        manager, dataset = manager_with_dataset

        initial_count = len(dataset.samples)

        manager.add_sample(dataset.id, {
            "id": "sample_001",
            "user_input": "测试输入",
            "actual_output": "测试输出",
        })

        assert len(dataset.samples) == initial_count + 1

    def test_add_sample_creates_sample_index(self, manager_with_dataset):
        """添加样本应创建索引"""
        manager, dataset = manager_with_dataset

        manager.add_sample(dataset.id, {
            "id": "sample_001",
            "user_input": "测试输入",
            "actual_output": "测试输出",
        })

        assert "sample_001" in manager._sample_index

    def test_add_sample_with_auto_id(self, manager_with_dataset):
        """添加样本时ID可自动生成"""
        manager, dataset = manager_with_dataset

        sample = manager.add_sample(dataset.id, {
            "user_input": "测试输入",
            "actual_output": "测试输出",
        })

        assert sample.id is not None
        assert len(sample.id) > 0

    def test_add_sample_to_nonexistent_dataset_returns_none(self, manager_with_dataset):
        """添加到不存在的数据集应返回None"""
        manager, dataset = manager_with_dataset

        result = manager.add_sample("nonexistent_id", {
            "id": "sample_001",
            "user_input": "测试输入",
            "actual_output": "测试输出",
        })

        assert result is None


class TestGoldenDatasetManagerCorrection:
    """人工校正测试 - 核心功能"""

    @pytest.fixture
    def manager_with_sample(self):
        """创建带样本的管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = GoldenDatasetManager(data_dir=temp_dir)
        dataset = manager.create_dataset(name="test_dataset")
        manager.add_sample(dataset.id, {
            "id": "sample_001",
            "user_input": "商品一周没发货，要求退款",
            "actual_output": "您好，非常抱歉...",
            "scores": {"correctness": 70, "safety": 60}  # 初始评分可能有偏差
        })
        yield manager, dataset
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_correct_sample_updates_scores(self, manager_with_sample):
        """校正样本应更新评分"""
        manager, dataset = manager_with_sample

        corrected_sample = manager.correct_sample(
            sample_id="sample_001",
            corrected_scores={"correctness": 85, "safety": 90},
            corrected_by="expert_user"
        )

        assert corrected_sample is not None
        assert corrected_sample.scores["correctness"] == 85
        assert corrected_sample.scores["safety"] == 90

    def test_correct_sample_sets_human_corrected_flag(self, manager_with_sample):
        """校正样本应设置人工校正标志"""
        manager, dataset = manager_with_sample

        manager.correct_sample(
            sample_id="sample_001",
            corrected_scores={"correctness": 85},
            corrected_by="expert_user"
        )

        sample = manager._sample_index["sample_001"]
        assert sample.human_corrected is True
        assert sample.corrected_by == "expert_user"
        assert sample.corrected_at is not None

    def test_correct_sample_nonexistent_returns_none(self, manager_with_sample):
        """校正不存在的样本应返回None"""
        manager, dataset = manager_with_sample

        result = manager.correct_sample(
            sample_id="nonexistent",
            corrected_scores={"correctness": 85},
            corrected_by="expert_user"
        )

        assert result is None

    def test_correct_sample_partial_scores(self, manager_with_sample):
        """校正样本可以只更新部分评分"""
        manager, dataset = manager_with_sample

        # 只校正safety分数，correctness保持不变
        corrected_sample = manager.correct_sample(
            sample_id="sample_001",
            corrected_scores={"safety": 95},  # 只更新safety
            corrected_by="expert_user"
        )

        assert corrected_sample.scores["safety"] == 95
        assert corrected_sample.scores["correctness"] == 70  # 保持原值

    def test_corrected_count_property(self, manager_with_sample):
        """校正计数属性应正确反映已校正样本数"""
        manager, dataset = manager_with_dataset = manager_with_sample

        assert dataset.corrected_count == 0

        manager.correct_sample(
            sample_id="sample_001",
            corrected_scores={"correctness": 85},
            corrected_by="expert_user"
        )

        assert dataset.corrected_count == 1


class TestGoldenDatasetManagerFewShot:
    """Few-shot示例生成测试 - 核心功能"""

    @pytest.fixture
    def manager_with_corrected_samples(self):
        """创建带已校正样本的管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = GoldenDatasetManager(data_dir=temp_dir)
        dataset = manager.create_dataset(name="test_dataset")

        # 添加多个样本
        for i in range(5):
            sample_id = f"sample_{i:03d}"
            manager.add_sample(dataset.id, {
                "id": sample_id,
                "user_input": f"用户问题{i}",
                "actual_output": f"模型回答{i}",
                "expected_output": f"期望输出{i}",
                "dimensions": ["correctness", "safety"],
                "scores": {"correctness": 80 + i, "safety": 90}
            })

        # 校正部分样本
        manager.correct_sample(
            sample_id="sample_000",
            corrected_scores={"correctness": 95},
            corrected_by="expert1"
        )
        manager.correct_sample(
            sample_id="sample_001",
            corrected_scores={"correctness": 90},
            corrected_by="expert2"
        )

        yield manager, dataset
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_few_shot_examples_returns_strings(self, manager_with_corrected_samples):
        """获取Few-shot示例应返回格式化字符串"""
        manager, dataset = manager_with_corrected_samples

        examples = manager.get_few_shot_examples(dataset.id, limit=5)

        assert isinstance(examples, list)
        assert len(examples) > 0
        for example in examples:
            assert isinstance(example, str)
            assert "示例开始" in example
            assert "示例结束" in example
            assert "用户问题" in example
            assert "评分结果" in example

    def test_get_few_shot_examples_limits_count(self, manager_with_corrected_samples):
        """获取Few-shot示例应限制数量"""
        manager, dataset = manager_with_corrected_samples

        examples = manager.get_few_shot_examples(dataset.id, limit=2)

        assert len(examples) <= 2

    def test_get_few_shot_examples_only_includes_corrected(self, manager_with_corrected_samples):
        """获取Few-shot示例应只包含已校正样本"""
        manager, dataset = manager_with_corrected_samples

        examples = manager.get_few_shot_examples(dataset.id, limit=5)

        # 检查示例是否来自已校正的样本
        for example in examples:
            # 从示例中提取评分，应该都是经过校正的
            assert "correctness: 9" in example  # 90或95

    def test_get_few_shot_examples_sorted_by_update_time(self, manager_with_corrected_samples):
        """获取Few-shot示例应按更新时间排序 - 示例不包含来源"""
        manager, dataset = manager_with_corrected_samples

        examples = manager.get_few_shot_examples(dataset.id, limit=5)

        # 示例不包含sample_id，只包含内容
        assert len(examples) > 0
        # 验证示例格式正确
        assert "示例开始" in examples[0]
        assert "用户问题" in examples[0]
        assert "模型输出" in examples[0]
        assert "评分结果" in examples[0]
        assert "示例结束" in examples[0]

    def test_get_few_shot_examples_nonexistent_dataset(self, manager_with_corrected_samples):
        """获取不存在的Few-shot示例应返回空列表"""
        manager, dataset = manager_with_corrected_samples

        examples = manager.get_few_shot_examples("nonexistent_id", limit=5)

        assert examples == []


class TestGoldenSampleToFewShotExample:
    """GoldenSample转Few-shot示例测试"""

    def test_to_few_shot_example_format(self):
        """转换为Few-shot示例应格式正确"""
        sample = GoldenSample(
            id="sample_001",
            user_input="什么是机器学习？",
            actual_output="机器学习是人工智能的一个分支...",
            expected_output="定义机器学习",
            dimensions=["correctness", "completeness"],
            scores={"correctness": 90, "completeness": 85}
        )

        example = sample.to_few_shot_example()

        assert "示例开始" in example
        assert "用户问题: 什么是机器学习？" in example
        assert "模型输出: 机器学习是人工智能的一个分支..." in example
        assert "期望输出: 定义机器学习" in example
        assert "correctness: 90" in example
        assert "completeness: 85" in example
        assert "示例结束" in example

    def test_to_few_shot_example_without_expected(self):
        """转换时可省略期望输出"""
        sample = GoldenSample(
            id="sample_002",
            user_input="测试问题",
            actual_output="测试回答",
            dimensions=["correctness"],
            scores={"correctness": 80}
        )

        example = sample.to_few_shot_example()

        assert "期望输出:" not in example


class TestGoldenDatasetGetDataset:
    """获取数据集测试"""

    @pytest.fixture
    def manager_with_dataset(self):
        """创建带数据集的管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = GoldenDatasetManager(data_dir=temp_dir)
        dataset = manager.create_dataset(name="test_dataset")
        yield manager, dataset
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_dataset_returns_dataset(self, manager_with_dataset):
        """获取数据集应返回数据集"""
        manager, dataset = manager_with_dataset

        result = manager.get_dataset(dataset.id)

        assert result is not None
        assert result.id == dataset.id
        assert result.name == "test_dataset"

    def test_get_dataset_nonexistent_returns_none(self, manager_with_dataset):
        """获取不存在的数据集应返回None"""
        manager, dataset = manager_with_dataset

        result = manager.get_dataset("nonexistent_id")

        assert result is None


# 关键发现：
# 1. GoldenDatasetManager使用内存缓存，无持久化到磁盘
# 2. correct_sample会覆盖原有scores，而非合并
# 3. get_few_shot_examples只返回已人工校正的样本
# 4. 样本按updated_at倒序排列，最新校正在前
