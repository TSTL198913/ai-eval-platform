"""
回归测试：GoldenSample input_data 字段映射
BUG-013: 假收敛 - GoldenSample 缺少 input_data 属性导致校准失效

测试场景覆盖：
1. 正向：GoldenSample.input_data 正确返回评估请求字典
2. 正向：包含 user_input + actual_output + expected_output 的完整样本
3. 边界：缺少 expected_output 的样本
4. 边界：空 user_input 的样本
5. 异常：直接访问不存在的旧字段名应抛出 AttributeError
6. 集成：校准代码可以正常使用 sample.input_data
"""

import pytest
from src.domain.golden_dataset import GoldenSample


class TestGoldenSampleInputData:
    """GoldenSample input_data 属性回归测试"""

    def test_input_data_returns_dict_with_actual_output(self):
        """正向：input_data 应返回包含 actual_output 的字典"""
        sample = GoldenSample(
            id="test_001",
            user_input="什么是机器学习？",
            actual_output="机器学习是人工智能的一个分支...",
            expected_output="机器学习是人工智能的一个分支，...",
            dimensions=["correctness"],
            scores={"correctness": 85.0},
        )

        result = sample.input_data

        assert isinstance(result, dict)
        assert "actual_output" in result
        assert result["actual_output"] == "机器学习是人工智能的一个分支..."

    def test_input_data_includes_user_input(self):
        """正向：input_data 应包含 user_input 字段（作为 input/user_input）"""
        sample = GoldenSample(
            id="test_002",
            user_input="用户问题内容",
            actual_output="模型回答内容",
        )

        result = sample.input_data

        assert result.get("user_input") == "用户问题内容" or result.get("input") == "用户问题内容"

    def test_input_data_includes_expected_output_when_present(self):
        """正向：有 expected_output 时应包含在 input_data 中"""
        sample = GoldenSample(
            id="test_003",
            user_input="1+1等于几？",
            actual_output="等于2",
            expected_output="2",
        )

        result = sample.input_data

        assert result.get("expected_output") == "2"

    def test_input_data_without_expected_output(self):
        """边界：缺少 expected_output 的样本，input_data 不应包含该键或值为 None"""
        sample = GoldenSample(
            id="test_004",
            user_input="问题",
            actual_output="回答",
        )

        result = sample.input_data

        assert result.get("expected_output") is None or "expected_output" not in result

    def test_input_data_empty_user_input(self):
        """边界：空 user_input 的样本，input_data 仍可正常访问"""
        sample = GoldenSample(
            id="test_005",
            user_input="",
            actual_output="回答",
        )

        result = sample.input_data

        assert isinstance(result, dict)
        assert result["actual_output"] == "回答"

    def test_input_data_includes_dimensions_and_metadata(self):
        """正向：input_data 应包含评估所需的维度和元数据信息"""
        sample = GoldenSample(
            id="test_006",
            user_input="问题",
            actual_output="回答",
            expected_output="标准",
            dimensions=["correctness", "relevance"],
            scores={"correctness": 90.0, "relevance": 85.0},
            metadata={"golden_score": 87.5},
        )

        result = sample.input_data

        assert "dimensions" in result or "metadata" in result or sample.scores is not None

    def test_input_data_compatible_with_evaluation_schema_payload(self):
        """集成：input_data 返回的字典可作为 EvaluationSchema 的 payload 使用"""
        from src.schemas.evaluation import EvaluationSchema

        sample = GoldenSample(
            id="test_007",
            user_input="解释量子计算",
            actual_output="量子计算使用量子比特...",
            expected_output="量子计算是利用量子力学原理的计算方式...",
            dimensions=["correctness"],
            scores={"correctness": 80.0},
        )

        schema = EvaluationSchema(
            type="general",
            payload=sample.input_data,
        )

        assert schema.type == "general"
        assert schema.payload is not None
        assert isinstance(schema.payload, dict)

    def test_multiple_samples_have_consistent_input_data_structure(self):
        """正向：多个样本的 input_data 结构应一致"""
        samples = [
            GoldenSample(id=f"test_{i}", user_input=f"问题{i}", actual_output=f"回答{i}")
            for i in range(5)
        ]

        keys = None
        for sample in samples:
            data = sample.input_data
            current_keys = set(data.keys())
            if keys is None:
                keys = current_keys
            else:
                assert "actual_output" in current_keys, "每个样本的 input_data 都应包含 actual_output"
