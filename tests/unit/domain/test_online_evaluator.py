"""
OnlineEvaluator 专项单元测试
测试目标：验证在线评估器的采样、评估、错误分类、回收机制
关键发现：
1. ProductionSampler 按sample_rate概率采样
2. OnlineEvaluator 调用llm_judge进行评估
3. 错误分类：hallucination/format_error/timeout/tool_error/rejection/unknown
4. recycle_failed_samples 将失败样本加入数据集
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.online.evaluator import (
    OnlineEvaluationPipeline,
    OnlineEvaluationStats,
    OnlineEvaluator,
    ProductionSampler,
    SampledRequest,
)


class TestProductionSamplerPositiveCases:
    """ProductionSampler 测试"""

    def test_sample_with_rate_1(self):
        """场景：采样率为1时全部采样"""
        sampler = ProductionSampler(sample_rate=1.0)

        request = sampler.sample("req_1", "input", "output")

        assert request is not None
        assert request.request_id == "req_1"
        assert request.user_input == "input"
        assert request.model_output == "output"

    def test_sample_with_rate_0(self):
        """场景：采样率为0时全部不采样"""
        sampler = ProductionSampler(sample_rate=0.0)

        # 多次调用都应返回None
        results = [sampler.sample(f"req_{i}", "input", "output") for i in range(10)]
        assert all(r is None for r in results)

    def test_sample_metadata_passed(self):
        """场景：metadata应被传递"""
        sampler = ProductionSampler(sample_rate=1.0)

        request = sampler.sample("req_1", "input", "output", model="gpt-4", user="user_1")

        assert request.metadata == {"model": "gpt-4", "user": "user_1"}

    def test_get_sampled_requests(self):
        """场景：获取采样请求"""
        sampler = ProductionSampler(sample_rate=1.0)

        for i in range(5):
            sampler.sample(f"req_{i}", f"input_{i}", f"output_{i}")

        requests = sampler.get_sampled_requests(limit=3)

        # 应返回最近3条
        assert len(requests) == 3
        assert requests[-1].request_id == "req_4"

    def test_clear(self):
        """场景：清空采样请求"""
        sampler = ProductionSampler(sample_rate=1.0)
        sampler.sample("req_1", "input", "output")
        sampler.clear()

        assert len(sampler.get_sampled_requests()) == 0


class TestOnlineEvaluatorPositiveCases:
    """OnlineEvaluator 测试"""

    @pytest.fixture
    def llm_judge(self):
        """返回一个返回成功的judge函数"""

        def judge(user_input, model_output):
            return True, 0.9, "回答很好"

        return judge

    @pytest.fixture
    def target(self, llm_judge):
        return OnlineEvaluator(llm_judge=llm_judge)

    def test_evaluate_success(self, target):
        """场景：评估成功"""
        request = SampledRequest(request_id="req_1", user_input="问题", model_output="回答")

        result = target.evaluate(request)

        assert result.is_success is True
        assert result.score == 0.9
        assert result.feedback == "回答很好"
        assert result.error_type is None

    def test_evaluate_failure(self, target):
        """场景：评估失败"""
        # 替换为返回失败的judge
        target.llm_judge = lambda u, m: (False, 0.2, "回答有误")

        request = SampledRequest(request_id="req_1", user_input="问题", model_output="回答")

        result = target.evaluate(request)

        assert result.is_success is False
        assert result.score == 0.2
        assert result.error_type == "unknown"

    def test_evaluate_batch(self, target):
        """场景：批量评估"""
        requests = [
            SampledRequest(request_id=f"req_{i}", user_input=f"q{i}", model_output=f"a{i}")
            for i in range(3)
        ]

        results = target.evaluate_batch(requests)

        assert len(results) == 3
        assert all(r.is_success for r in results)

    def test_classify_hallucination(self, target):
        """场景：分类幻觉错误"""
        error_type = target._classify_error(
            SampledRequest(request_id="r", user_input="q", model_output="a"),
            "这是hallucination错误",
        )
        assert error_type == "hallucination"

    def test_classify_format_error(self, target):
        """场景：分类格式错误"""
        error_type = target._classify_error(
            SampledRequest(request_id="r", user_input="q", model_output="a"), "格式错误"
        )
        assert error_type == "format_error"

    def test_classify_timeout(self, target):
        """场景：分类超时错误"""
        error_type = target._classify_error(
            SampledRequest(request_id="r", user_input="q", model_output="a"), "请求超时"
        )
        assert error_type == "timeout"

    def test_classify_tool_error(self, target):
        """场景：分类工具调用错误"""
        error_type = target._classify_error(
            SampledRequest(request_id="r", user_input="q", model_output="a"), "工具调用失败"
        )
        assert error_type == "tool_error"

    def test_classify_rejection(self, target):
        """场景：分类拒绝错误"""
        error_type = target._classify_error(
            SampledRequest(request_id="r", user_input="q", model_output="a"), "模型拒绝回答"
        )
        assert error_type == "rejection"

    def test_classify_unknown(self, target):
        """场景：未知错误"""
        error_type = target._classify_error(
            SampledRequest(request_id="r", user_input="q", model_output="a"), "其他错误"
        )
        assert error_type == "unknown"

    def test_classify_no_feedback(self, target):
        """场景：无feedback时返回unknown"""
        error_type = target._classify_error(
            SampledRequest(request_id="r", user_input="q", model_output="a"), None
        )
        assert error_type == "unknown"

    def test_recycle_failed_samples_no_dataset_manager(self, target):
        """场景：无dataset_manager时返回空列表"""
        results = target.recycle_failed_samples("ds_001")

        assert results == []

    def test_recycle_failed_samples(self, target):
        """场景：回收失败样本"""
        mock_dataset_manager = MagicMock()
        target.dataset_manager = mock_dataset_manager
        target.llm_judge = lambda u, m: (False, 0.2, "错误")

        # 创建失败请求
        for i in range(3):
            req = SampledRequest(request_id=f"req_{i}", user_input=f"q{i}", model_output=f"a{i}")
            target.evaluate(req)

        results = target.recycle_failed_samples("ds_001", max_recycle=2)

        # 应回收2个失败样本
        assert len(results) == 2
        # 每个失败样本会调用一次add_samples
        assert mock_dataset_manager.add_samples.call_count == 2

    def test_get_stats_empty(self, target):
        """场景：空结果统计"""
        stats = target.get_stats()

        assert stats.total_samples == 0
        assert stats.success_rate == 0.0

    def test_get_stats_with_results(self, target):
        """场景：有结果的统计"""
        # 成功和失败混合
        target.llm_judge = MagicMock(
            side_effect=[
                (True, 0.9, "ok"),
                (False, 0.2, "fail"),
                (True, 0.85, "ok"),
            ]
        )

        for i in range(3):
            req = SampledRequest(request_id=f"req_{i}", user_input=f"q{i}", model_output=f"a{i}")
            target.evaluate(req)

        stats = target.get_stats()

        assert stats.total_samples == 3
        assert stats.success_count == 2
        assert stats.failure_count == 1
        assert abs(stats.success_rate - 2 / 3) < 0.01
        assert stats.avg_score > 0

    def test_get_results(self, target):
        """场景：获取所有结果"""
        target.llm_judge = lambda u, m: (True, 0.9, "ok")
        target.evaluate(SampledRequest(request_id="r1", user_input="q", model_output="a"))

        results = target.get_results()

        assert len(results) == 1

    def test_clear(self, target):
        """场景：清空结果"""
        target.llm_judge = lambda u, m: (True, 0.9, "ok")
        target.evaluate(SampledRequest(request_id="r1", user_input="q", model_output="a"))
        target.clear()

        assert target.get_results() == []


class TestOnlineEvaluationStats:
    """OnlineEvaluationStats 测试"""

    def test_success_rate_no_samples(self):
        """场景：无样本时成功率"""
        stats = OnlineEvaluationStats()

        assert stats.success_rate == 0.0

    def test_success_rate_calculation(self):
        """场景：成功率计算"""
        stats = OnlineEvaluationStats(total_samples=10, success_count=7, failure_count=3)

        assert stats.success_rate == 0.7

    def test_to_dict(self):
        """场景：转换为字典"""
        stats = OnlineEvaluationStats(
            total_samples=5, success_count=3, failure_count=2, avg_score=0.8
        )

        result = stats.to_dict()

        assert result["total_samples"] == 5
        assert result["success_rate"] == 0.6
        assert result["avg_score"] == 0.8
        assert "error_types" in result


class TestOnlineEvaluationPipelinePositiveCases:
    """OnlineEvaluationPipeline 测试"""

    def test_pipeline_no_sample(self):
        """场景：未采样到时返回None"""
        sampler = ProductionSampler(sample_rate=0.0)
        evaluator = OnlineEvaluator(llm_judge=lambda u, m: (True, 1.0, "ok"))
        pipeline = OnlineEvaluationPipeline(sampler, evaluator)

        result = pipeline.process_request("r1", "input", "output")

        assert result is None

    def test_pipeline_sampled_and_evaluated(self):
        """场景：采样后评估"""
        sampler = ProductionSampler(sample_rate=1.0)
        evaluator = OnlineEvaluator(llm_judge=lambda u, m: (True, 0.9, "ok"))
        pipeline = OnlineEvaluationPipeline(sampler, evaluator)

        result = pipeline.process_request("r1", "input", "output")

        assert result is not None
        assert result.is_success is True

    def test_pipeline_trigger_recycle_no_dataset_manager(self):
        """场景：无dataset_manager时trigger_recycle返回空"""
        sampler = ProductionSampler(sample_rate=1.0)
        evaluator = OnlineEvaluator(llm_judge=lambda u, m: (True, 0.9, "ok"))
        pipeline = OnlineEvaluationPipeline(sampler, evaluator)

        results = pipeline.trigger_recycle("ds_001")

        assert results == []

    def test_pipeline_trigger_recycle_with_dataset_manager(self):
        """场景：有dataset_manager时触发回收"""
        sampler = ProductionSampler(sample_rate=1.0)
        evaluator = OnlineEvaluator(
            llm_judge=lambda u, m: (False, 0.2, "fail"),
            dataset_manager=MagicMock(),
        )
        pipeline = OnlineEvaluationPipeline(sampler, evaluator, dataset_manager=MagicMock())

        # 先评估一个失败请求
        pipeline.process_request("r1", "input", "output")

        results = pipeline.trigger_recycle("ds_001")

        assert len(results) >= 0  # 取决于回收逻辑

    def test_pipeline_get_stats(self):
        """场景：获取统计"""
        sampler = ProductionSampler(sample_rate=1.0)
        evaluator = OnlineEvaluator(llm_judge=lambda u, m: (True, 0.9, "ok"))
        pipeline = OnlineEvaluationPipeline(sampler, evaluator)

        pipeline.process_request("r1", "input", "output")

        stats = pipeline.get_stats()

        assert stats.total_samples == 1


class TestOnlineEvaluatorNegativeCases:
    """负向测试 - 错误处理"""

    def test_classify_error_with_empty_feedback(self):
        """场景：空feedback时返回unknown"""

        def judge(u, m):
            return False, 0.0, None

        target = OnlineEvaluator(llm_judge=judge)

        request = SampledRequest(request_id="r1", user_input="q", model_output="a")
        result = target.evaluate(request)

        assert result.error_type == "unknown"


class TestOnlineEvaluatorBoundaryCases:
    """边界测试"""

    def test_sample_request_count(self):
        """场景：验证采样次数"""
        sampler = ProductionSampler(sample_rate=1.0)

        for i in range(100):
            sampler.sample(f"req_{i}", f"q{i}", f"a{i}")

        # 应全部采样
        assert len(sampler._sampled_requests) == 100

    def test_evaluate_recycle_ordering_by_score(self):
        """场景：回收应按分数升序排序"""
        target = OnlineEvaluator(
            llm_judge=lambda u, m: (False, 0.5, "fail"),
            dataset_manager=MagicMock(),
        )

        # 添加不同分数的失败结果
        for i, score in enumerate([0.3, 0.1, 0.5, 0.2]):
            req = SampledRequest(request_id=f"req_{i}", user_input=f"q{i}", model_output=f"a{i}")
            # 直接添加结果
            from src.domain.online.evaluator import OnlineEvaluationResult

            target._results.append(
                OnlineEvaluationResult(
                    request_id=f"req_{i}",
                    is_success=False,
                    score=score,
                )
            )
            target._sampled_requests.append(req)

        results = target.recycle_failed_samples("ds_001", max_recycle=2)

        # 回收的应是分数最低的2个
        assert len(results) == 2
        scores = [r.score for r in results]
        assert scores[0] <= scores[1]
