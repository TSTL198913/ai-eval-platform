"""
回归测试：Few-shot 动态Prompt自优化能力
新增：get_few_shot_examples 支持 dimensions 参数过滤

测试场景覆盖：
1. 正向：不传 dimensions 返回所有人工校正样本
2. 正向：传 dimensions 过滤返回匹配维度的样本
3. 边界：dimensions 为空列表时返回所有
4. 边界：无人工校正样本时返回空
5. 边界：dimensions 不匹配任何样本时返回空
6. 集成：返回的 few-shot 示例可拼接到评估器 Prompt 中
"""

import pytest
from datetime import datetime
from src.domain.golden_dataset import GoldenSample, GoldenDataset, GoldenDatasetManager


class TestFewShotDynamicOptimization:
    """Few-shot 动态Prompt自优化测试"""

    @pytest.fixture
    def dataset_with_samples(self):
        """创建含多种维度样本的数据集"""
        manager = GoldenDatasetManager()
        dataset = manager.create_dataset("few_shot_test", "few-shot测试", "test")

        samples = [
            GoldenSample(
                id="fs_001",
                user_input="问题1",
                actual_output="回答1",
                expected_output="标准1",
                dimensions=["correctness", "relevance"],
                scores={"correctness": 90, "relevance": 85},
                human_corrected=True,
            ),
            GoldenSample(
                id="fs_002",
                user_input="问题2",
                actual_output="回答2",
                expected_output="标准2",
                dimensions=["correctness", "fluency"],
                scores={"correctness": 80, "fluency": 75},
                human_corrected=True,
            ),
            GoldenSample(
                id="fs_003",
                user_input="问题3",
                actual_output="回答3",
                expected_output="标准3",
                dimensions=["safety"],
                scores={"safety": 95},
                human_corrected=True,
            ),
            GoldenSample(
                id="fs_004",
                user_input="问题4",
                actual_output="回答4",
                expected_output="标准4",
                dimensions=["correctness"],
                scores={"correctness": 60},
                human_corrected=False,
            ),
        ]

        for s in samples:
            dataset.samples.append(s)
            manager._sample_index[s.id] = s

        return manager, dataset.id

    def test_get_few_shot_without_dimensions(self, dataset_with_samples):
        """正向：不传 dimensions 返回所有人工校正样本"""
        manager, dataset_id = dataset_with_samples

        result = manager.get_few_shot_examples(dataset_id, limit=10)

        assert len(result) == 3, "应返回3个人工校正样本（排除 fs_004）"
        for example in result:
            assert "示例开始" in example

    def test_get_few_shot_with_dimensions_filter(self, dataset_with_samples):
        """正向：传 dimensions 过滤返回匹配维度的样本"""
        manager, dataset_id = dataset_with_samples

        result = manager.get_few_shot_examples(
            dataset_id, limit=10, dimensions=["correctness"]
        )

        assert len(result) == 2, "应返回2个包含 correctness 维度的样本"
        for example in result:
            assert "correctness" in example

    def test_get_few_shot_with_empty_dimensions(self, dataset_with_samples):
        """边界：dimensions 为空列表时返回所有人工校正样本"""
        manager, dataset_id = dataset_with_samples

        result = manager.get_few_shot_examples(dataset_id, limit=10, dimensions=[])

        assert len(result) == 3, "空 dimensions 应返回所有人工校正样本"

    def test_get_few_shot_no_corrected_samples(self):
        """边界：无人工校正样本时返回空"""
        manager = GoldenDatasetManager()
        dataset = manager.create_dataset("empty_ds", "空数据集", "test")
        manager.add_sample(dataset.id, {
            "user_input": "问题",
            "actual_output": "回答",
            "scores": {"overall": 80},
        })

        result = manager.get_few_shot_examples(dataset.id)

        assert result == [], "无人工校正样本时应返回空列表"

    def test_get_few_shot_dimensions_no_match(self, dataset_with_samples):
        """边界：dimensions 不匹配任何样本时返回空"""
        manager, dataset_id = dataset_with_samples

        result = manager.get_few_shot_examples(
            dataset_id, dimensions=["nonexistent_dimension"]
        )

        assert result == [], "不匹配的 dimensions 应返回空"

    def test_few_shot_examples_usable_in_prompt(self, dataset_with_samples):
        """集成：返回的 few-shot 示例可拼接到评估器 Prompt 中"""
        manager, dataset_id = dataset_with_samples

        examples = manager.get_few_shot_examples(dataset_id, limit=3)

        prompt_section = "\n".join(examples)
        assert "示例开始" in prompt_section
        assert "示例结束" in prompt_section
        assert "用户问题" in prompt_section
        assert "模型输出" in prompt_section
        assert "评分结果" in prompt_section

        full_prompt = f"请参考以下示例进行评估：\n\n{prompt_section}\n\n现在请评估以下回答："
        assert "请参考以下示例" in full_prompt
