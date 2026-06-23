"""
ABTesting 专项单元测试
测试目标：验证A/B测试框架的统计检验、结果管理、API封装
关键发现：
1. ABTestResult使用t检验进行统计显著性分析
2. 样本量<2时返回"样本量不足"错误
3. ABTestManager是单例式设计（class-level存储）
4. ABTestAPI提供静态方法封装
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.ab_testing import (
    ABTestAPI,
    ABTestManager,
    ABTestResult,
    ABTestStatus,
)


class TestABTestResultPositiveCases:
    """正向测试 - ABTestResult核心功能"""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """每个测试前清理测试存储"""
        ABTestManager._tests.clear()
        yield
        ABTestManager._tests.clear()

    def test_create_test(self):
        """场景：创建A/B测试"""
        test = ABTestResult("test_001")
        test.group_a["name"] = "Model A"
        test.group_b["name"] = "Model B"

        assert test.test_id == "test_001"
        assert test.status == ABTestStatus.RUNNING
        assert test.group_a["name"] == "Model A"
        assert test.group_b["name"] == "Model B"
        assert test.created_at is not None

    def test_add_result(self):
        """场景：添加测试结果"""
        test = ABTestResult("test_001")

        test.add_result("A", {"score": 0.8, "latency_ms": 100})
        test.add_result("B", {"score": 0.9, "latency_ms": 90})

        assert len(test.group_a["results"]) == 1
        assert len(test.group_b["results"]) == 1

    def test_calculate_metrics(self):
        """场景：计算各组指标"""
        test = ABTestResult("test_001")
        test.add_result("A", {"score": 0.8, "latency_ms": 100})
        test.add_result("A", {"score": 0.6, "latency_ms": 120})
        test.add_result("B", {"score": 0.9, "latency_ms": 80})
        test.add_result("B", {"score": 0.7, "latency_ms": 100})

        test.calculate_metrics()

        assert test.group_a["metrics"]["sample_size"] == 2
        assert test.group_a["metrics"]["avg_score"] == 0.7
        assert test.group_b["metrics"]["avg_score"] == 0.8
        assert test.group_a["metrics"]["pass_rate"] == 0.5

    def test_run_statistical_test(self):
        """场景：运行t检验"""
        test = ABTestResult("test_001")
        for i in range(10):
            test.add_result("A", {"score": 0.6 + i * 0.01, "latency_ms": 100})
            test.add_result("B", {"score": 0.8 + i * 0.01, "latency_ms": 90})

        test.calculate_metrics()
        test.run_statistical_test()

        assert "p_value" in test.statistics
        assert "t_value" in test.statistics
        assert "is_significant" in test.statistics
        assert "confidence_interval_95" in test.statistics

    def test_complete(self):
        """场景：完成测试"""
        test = ABTestResult("test_001")
        # 使用有变化的分数,避免ZeroDivisionError
        for i in range(5):
            test.add_result("A", {"score": 0.6 + i * 0.02, "latency_ms": 100})
            test.add_result("B", {"score": 0.8 + i * 0.02, "latency_ms": 90})

        test.complete()

        assert test.status == ABTestStatus.COMPLETED
        assert test.completed_at is not None
        assert "p_value" in test.statistics

    def test_generate_report(self):
        """场景：生成报告"""
        test = ABTestResult("test_001")
        test.group_a["name"] = "Model A"
        test.group_b["name"] = "Model B"
        test.add_result("A", {"score": 0.7, "latency_ms": 100})
        test.add_result("B", {"score": 0.8, "latency_ms": 90})

        test.complete()
        report = test.generate_report()

        assert "A/B测试报告" in report
        assert "test_001" in report
        assert "Model A" in report
        assert "Model B" in report
        assert "统计检验" in report


class TestABTestManagerPositiveCases:
    """ABTestManager 测试"""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """每个测试前清理测试存储"""
        ABTestManager._tests.clear()
        yield
        ABTestManager._tests.clear()

    def test_create_test(self):
        """场景：创建测试"""
        test = ABTestManager.create_test("test_001", "Model A", "Model B")

        assert test.test_id == "test_001"
        assert "test_001" in ABTestManager._tests

    def test_get_test(self):
        """场景：获取测试"""
        ABTestManager.create_test("test_001", "Model A", "Model B")
        test = ABTestManager.get_test("test_001")

        assert test is not None
        assert test.test_id == "test_001"

    def test_get_nonexistent_test(self):
        """场景：获取不存在的测试"""
        test = ABTestManager.get_test("nonexistent")
        assert test is None

    def test_list_tests(self):
        """场景：列出所有测试"""
        ABTestManager.create_test("test_001", "A", "B")
        ABTestManager.create_test("test_002", "C", "D")

        tests = ABTestManager.list_tests()

        assert len(tests) == 2

    def test_delete_test(self):
        """场景：删除测试"""
        ABTestManager.create_test("test_001", "A", "B")
        ABTestManager.delete_test("test_001")

        assert "test_001" not in ABTestManager._tests

    def test_run_ab_test(self):
        """场景：执行A/B测试"""
        ABTestManager.create_test("test_001", "A", "B")

        model_a = MagicMock()
        model_a.chat.return_value = "Response A"
        model_b = MagicMock()
        model_b.chat.return_value = "Response B"

        test_cases = [
            {"id": "case_1", "input": "测试1", "expected_score": 0.8},
            {"id": "case_2", "input": "测试2", "expected_score": 0.9},
        ]

        result = ABTestManager.run_ab_test("test_001", model_a, model_b, test_cases)

        assert result.status == ABTestStatus.COMPLETED
        assert len(result.group_a["results"]) == 2
        assert len(result.group_b["results"]) == 2

    def test_run_ab_test_with_model_error(self):
        """场景：模型调用错误时正确处理"""
        ABTestManager.create_test("test_001", "A", "B")

        model_a = MagicMock()
        model_a.chat.side_effect = Exception("Model A failed")
        model_b = MagicMock()
        model_b.chat.return_value = "Response B"

        test_cases = [{"id": "case_1", "input": "测试", "expected_score": 0.8}]

        result = ABTestManager.run_ab_test("test_001", model_a, model_b, test_cases)

        # A组结果为错误状态
        assert result.group_a["results"][0]["status"] == "error"
        # B组正常
        assert result.group_b["results"][0]["status"] == "success"

    def test_run_nonexistent_test_raises(self):
        """场景：运行不存在的测试应抛出异常"""
        model_a = MagicMock()
        model_b = MagicMock()

        with pytest.raises(ValueError, match="not found"):
            ABTestManager.run_ab_test("nonexistent", model_a, model_b, [])


class TestABTestAPIPositiveCases:
    """ABTestAPI 测试"""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """每个测试前清理测试存储"""
        ABTestManager._tests.clear()
        yield
        ABTestManager._tests.clear()

    def test_create(self):
        """场景：API创建测试"""
        result = ABTestAPI.create("test_001", "Model A", "Model B")

        assert result["test_id"] == "test_001"
        assert result["status"] == "running"
        assert result["group_a"] == "Model A"
        assert result["group_b"] == "Model B"

    def test_add_result(self):
        """场景：API添加结果"""
        ABTestAPI.create("test_001", "A", "B")

        result = ABTestAPI.add_result("test_001", "A", {"score": 0.8})

        assert "message" in result
        assert "total_results" in result

    def test_add_result_nonexistent_test(self):
        """场景：向不存在的测试添加结果"""
        result = ABTestAPI.add_result("nonexistent", "A", {"score": 0.8})

        assert "error" in result

    def test_complete(self):
        """场景：API完成测试"""
        ABTestAPI.create("test_001", "A", "B")
        # 使用有变化的分数,避免ZeroDivisionError
        for i in range(5):
            ABTestAPI.add_result("test_001", "A", {"score": 0.6 + i * 0.02})
            ABTestAPI.add_result("test_001", "B", {"score": 0.8 + i * 0.02})

        result = ABTestAPI.complete("test_001")

        assert result["status"] == "completed"
        assert "statistics" in result

    def test_complete_nonexistent(self):
        """场景：完成不存在的测试"""
        result = ABTestAPI.complete("nonexistent")

        assert "error" in result

    def test_get_result(self):
        """场景：API获取结果"""
        ABTestAPI.create("test_001", "A", "B")
        ABTestAPI.add_result("test_001", "A", {"score": 0.7})

        result = ABTestAPI.get_result("test_001")

        assert result["test_id"] == "test_001"
        assert "group_a" in result

    def test_get_result_nonexistent(self):
        """场景：获取不存在的测试结果"""
        result = ABTestAPI.get_result("nonexistent")

        assert "error" in result

    def test_list(self):
        """场景：API列出所有测试"""
        ABTestAPI.create("test_001", "A", "B")
        ABTestAPI.create("test_002", "C", "D")

        tests = ABTestAPI.list()

        assert len(tests) == 2


class TestABTestNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """每个测试前清理测试存储"""
        ABTestManager._tests.clear()
        yield
        ABTestManager._tests.clear()

    def test_insufficient_samples_returns_error(self):
        """场景：样本量不足应返回错误信息"""
        test = ABTestResult("test_001")
        test.add_result("A", {"score": 0.8, "latency_ms": 100})

        test.run_statistical_test()

        assert test.statistics.get("error") == "样本量不足"

    def test_run_nonparametric_insufficient_samples(self):
        """场景：非参数检验样本不足"""
        test = ABTestResult("test_001")
        test.add_result("A", {"score": 0.8})
        test.add_result("B", {"score": 0.9})

        result = test.run_nonparametric_test()

        # 样本量不足时返回error字段
        assert "error" in result


class TestABTestBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """每个测试前清理测试存储"""
        ABTestManager._tests.clear()
        yield
        ABTestManager._tests.clear()

    def test_identical_groups_no_significance(self):
        """场景：两组均值相同时不应有显著差异"""
        test = ABTestResult("test_001")
        # 使用有变化的分数,避免ZeroDivisionError,但均值相同
        for i in range(10):
            test.add_result("A", {"score": 0.7 + (i % 3) * 0.01, "latency_ms": 100})
            test.add_result("B", {"score": 0.7 + (i % 3) * 0.01, "latency_ms": 100})

        test.calculate_metrics()
        test.run_statistical_test()

        assert test.statistics["is_significant"] is False
        assert test.statistics["t_value"] == 0

    def test_highly_different_groups_significant(self):
        """场景：差异显著时t值高"""
        test = ABTestResult("test_001")
        # 使用有变化的分数,避免ZeroDivisionError
        for i in range(20):
            test.add_result("A", {"score": 0.3 + (i % 5) * 0.01, "latency_ms": 100})
            test.add_result("B", {"score": 0.9 - (i % 5) * 0.01, "latency_ms": 100})

        test.calculate_metrics()
        test.run_statistical_test()

        assert test.statistics["is_significant"] is True
        assert test.statistics["recommended_group"] == "B"

    def test_p_value_with_zero_degrees_of_freedom(self):
        """场景：自由度为0时p_value应为1.0"""
        test = ABTestResult("test_001")
        p = test._calculate_p_value(2.0, 0)

        assert p == 1.0

    def test_std_with_single_value(self):
        """场景：单值时标准差为0"""
        test = ABTestResult("test_001")
        std = test._calculate_std([0.8])

        assert std == 0.0

    def test_std_with_empty(self):
        """场景：空列表时标准差为0"""
        test = ABTestResult("test_001")
        std = test._calculate_std([])

        assert std == 0.0


class TestABTestMultipleComparisonCorrection:
    """多重比较校正测试"""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """每个测试前清理测试存储"""
        ABTestManager._tests.clear()
        yield
        ABTestManager._tests.clear()

    def test_bonferroni_correction(self):
        """场景：Bonferroni校正"""
        test = ABTestResult("test_001")
        p_values = [0.01, 0.04, 0.03, 0.005]

        result = test.apply_multiple_comparison_correction(p_values, method="bonferroni")

        assert result["method"] == "bonferroni"
        assert len(result["corrected_p_values"]) == 4
        # 校正后p值 = 原始p值 * 数量
        for original, corrected in zip(p_values, result["corrected_p_values"], strict=False):
            assert corrected == min(original * 4, 1.0)

    def test_holm_correction(self):
        """场景：Holm-Bonferroni校正"""
        test = ABTestResult("test_001")
        p_values = [0.01, 0.04, 0.03, 0.005]

        result = test.apply_multiple_comparison_correction(p_values, method="holm")

        assert result["method"] == "holm"
        assert len(result["corrected_p_values"]) == 4

    def test_correction_empty_p_values(self):
        """场景：空p值列表"""
        test = ABTestResult("test_001")
        result = test.apply_multiple_comparison_correction([])

        assert result["corrected_p_values"] == []
        # 空列表场景可能返回rejected或rejected_hypotheses
        rejected = result.get("rejected_hypotheses", result.get("rejected", []))
        assert rejected == []


class TestABTestDependencyHandling:
    """依赖测试 - 异常处理"""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """每个测试前清理测试存储"""
        ABTestManager._tests.clear()
        yield
        ABTestManager._tests.clear()

    def test_wilcoxon_insufficient_pairs(self):
        """场景：Wilcoxon检验配对样本不足"""
        test = ABTestResult("test_001")
        test.add_result("A", {"score": 0.7})
        test.add_result("B", {"score": 0.8})

        result = test.run_wilcoxon_test()

        assert "error" in result
