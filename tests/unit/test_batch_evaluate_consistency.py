"""批量评估一致性测试

验证批量评估与单次评估结果一致，确保走同一校准+熔断+降级路径。
"""

import pytest
from unittest.mock import Mock, patch

from src.domain.evaluators.base import BaseEvaluator
from src.schemas.evaluation import EvaluationSchema
from src.schemas.evaluation import EvaluatorStatus
from src.schemas.evaluation import DomainResponse


class TestBatchEvaluateConsistency:
    """批量评估一致性测试"""

    def test_batch_evaluate_uses_safe_evaluate(self):
        """验证batch_evaluate调用safe_evaluate"""
        evaluator = Mock(spec=BaseEvaluator)
        
        mock_response = DomainResponse(
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
            data={"reason": "test"},
        )
        
        evaluator.safe_evaluate = Mock(return_value=mock_response)
        
        requests = [
            EvaluationSchema(id="test1", type="general", payload={"actual_output": "a", "expected_output": "b"}),
            EvaluationSchema(id="test2", type="general", payload={"actual_output": "c", "expected_output": "d"}),
        ]
        
        results = BaseEvaluator.batch_evaluate(evaluator, requests)
        
        assert len(results) == 2
        assert evaluator.safe_evaluate.call_count == 2
        assert all(r.evaluation_status == EvaluatorStatus.SUCCESS for r in results)

    def test_batch_evaluate_single_failure(self):
        """验证批量评估中单条失败不影响其他请求"""
        evaluator = Mock(spec=BaseEvaluator)
        
        success_response = DomainResponse(
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
            data={"reason": "test"},
        )
        error_response = DomainResponse(
            score=0.0,
            evaluation_status=EvaluatorStatus.ERROR,
            error="批量评估失败: Test error",
        )
        
        evaluator.safe_evaluate = Mock(side_effect=[success_response, RuntimeError("Test error")])
        evaluator.create_error_response = Mock(return_value=error_response)
        
        requests = [
            EvaluationSchema(id="test1", type="general", payload={"actual_output": "a", "expected_output": "b"}),
            EvaluationSchema(id="test2", type="general", payload={"actual_output": "c", "expected_output": "d"}),
        ]
        
        results = BaseEvaluator.batch_evaluate(evaluator, requests)
        
        assert len(results) == 2
        assert results[0].evaluation_status == EvaluatorStatus.SUCCESS
        assert results[1].evaluation_status == EvaluatorStatus.ERROR

    def test_batch_evaluate_returns_ordered_results(self):
        """验证批量评估返回结果顺序与输入一致"""
        evaluator = Mock(spec=BaseEvaluator)
        
        def make_response(idx):
            return DomainResponse(
                score=0.7 + idx * 0.1,
                evaluation_status=EvaluatorStatus.SUCCESS,
                confidence=0.9,
                data={"index": idx},
            )
        
        evaluator.safe_evaluate = Mock(side_effect=[make_response(i) for i in range(5)])
        
        requests = [
            EvaluationSchema(id=f"test{i}", type="general", payload={"idx": i})
            for i in range(5)
        ]
        
        results = BaseEvaluator.batch_evaluate(evaluator, requests)
        
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.score == pytest.approx(0.7 + i * 0.1)
            assert result.data["index"] == i

    @pytest.mark.asyncio
    async def test_batch_evaluate_async_uses_safe_evaluate_async(self):
        """验证batch_evaluate_async调用safe_evaluate_async"""
        evaluator = Mock(spec=BaseEvaluator)
        
        mock_response = DomainResponse(
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
            data={"reason": "test"},
        )
        
        async def async_response(req):
            return mock_response
        
        evaluator.safe_evaluate_async = Mock(side_effect=async_response)
        
        requests = [
            EvaluationSchema(id="test1", type="general", payload={"actual_output": "a", "expected_output": "b"}),
            EvaluationSchema(id="test2", type="general", payload={"actual_output": "c", "expected_output": "d"}),
        ]
        
        results = await BaseEvaluator.batch_evaluate_async(evaluator, requests)
        
        assert len(results) == 2
        assert evaluator.safe_evaluate_async.call_count == 2
        assert all(r.evaluation_status == EvaluatorStatus.SUCCESS for r in results)

    def test_batch_and_single_evaluate_same_path(self):
        """验证批量和单次评估走同一评估路径"""
        evaluator = Mock(spec=BaseEvaluator)
        
        mock_response = DomainResponse(
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
            data={"reason": "test"},
        )
        
        evaluator.safe_evaluate = Mock(return_value=mock_response)
        
        single_request = EvaluationSchema(id="single", type="general", payload={"actual_output": "a", "expected_output": "b"})
        batch_requests = [single_request]
        
        single_result = evaluator.safe_evaluate(single_request)
        batch_results = BaseEvaluator.batch_evaluate(evaluator, batch_requests)
        
        assert evaluator.safe_evaluate.call_count == 2
        assert single_result.score == batch_results[0].score
        assert single_result.evaluation_status == batch_results[0].evaluation_status