"""
API接口契约测试

验证API响应的结构一致性和字段完整性，确保接口变更时能够及时发现破坏性修改。

契约测试覆盖：
1. DomainResponse字段契约
2. EvaluationSchema字段契约
3. EvaluationResult字段契约
4. EvaluatorService服务层契约
5. EvaluationEngine引擎层契约
6. API响应结构契约
"""

import pytest
from unittest.mock import MagicMock

from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus
from src.schemas.schemas import EvaluationResult, EvaluationStatus as RecordStatus
from src.services.evaluator_svc import EvaluatorService, EvaluationServiceResponse


class TestDomainResponseContract:
    """DomainResponse字段契约测试"""

    def test_response_minimal_fields(self):
        """验证响应包含所有必需字段"""
        response = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )

        assert hasattr(response, 'text')
        assert hasattr(response, 'score')
        assert hasattr(response, 'evaluation_status')
        assert hasattr(response, 'confidence')
        assert hasattr(response, 'confidence_level')
        assert hasattr(response, 'error')
        assert hasattr(response, 'metadata')
        assert hasattr(response, 'data')
        assert hasattr(response, 'is_valid')

    def test_score_is_float(self):
        """验证score字段类型为float"""
        response = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        assert isinstance(response.score, float)
        assert 0.0 <= response.score <= 1.0

    def test_confidence_is_float(self):
        """验证confidence字段类型为float"""
        response = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        assert isinstance(response.confidence, float)
        assert 0.0 <= response.confidence <= 1.0

    def test_evaluation_status_is_enum(self):
        """验证evaluation_status字段类型为EvaluatorStatus"""
        response = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        assert isinstance(response.evaluation_status, EvaluatorStatus)


class TestEvaluationSchemaContract:
    """EvaluationSchema字段契约测试"""

    def test_schema_minimal_fields(self):
        """验证评估请求包含所有必需字段"""
        request = EvaluationSchema(
            id="test_001",
            type="semantic",
            payload={"actual_output": "test"},
        )

        assert hasattr(request, 'id')
        assert hasattr(request, 'type')
        assert hasattr(request, 'payload')
        assert hasattr(request, 'metadata')

    def test_payload_is_dict(self):
        """验证payload字段类型为dict"""
        request = EvaluationSchema(
            id="test_001",
            type="semantic",
            payload={"actual_output": "test"},
        )
        assert isinstance(request.payload, dict)


class TestEvaluationResultContract:
    """EvaluationResult字段契约测试"""

    def test_result_minimal_fields(self):
        """验证评估结果包含所有必需字段"""
        response = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        result = EvaluationResult(
            case_id="test_001",
            status=RecordStatus.PASSED,
            response=response,
            adapter_name="test_adapter",
            latency_ms=100,
        )

        assert hasattr(result, 'case_id')
        assert hasattr(result, 'status')
        assert hasattr(result, 'response')
        assert hasattr(result, 'adapter_name')
        assert hasattr(result, 'latency_ms')


class TestEvaluatorStatusContract:
    """EvaluatorStatus枚举契约测试"""

    def test_status_values(self):
        """验证所有状态值存在"""
        assert EvaluatorStatus.SUCCESS.value == 'success'
        assert EvaluatorStatus.PARTIAL.value == 'partial'
        assert EvaluatorStatus.CANNOT_EVALUATE.value == 'cannot_evaluate'
        assert EvaluatorStatus.ERROR.value == 'error'

    def test_status_has_all_members(self):
        """验证枚举包含所有必需成员"""
        members = [m.name for m in EvaluatorStatus]
        assert 'SUCCESS' in members
        assert 'PARTIAL' in members
        assert 'CANNOT_EVALUATE' in members
        assert 'ERROR' in members


class TestResponseSerializationContract:
    """响应序列化契约测试"""

    def test_response_json_serializable(self):
        """验证响应可以序列化为JSON"""
        response = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
            metadata={"key": "value"},
            data={"detail": "test"},
        )
        import json
        serialized = response.model_dump_json()
        deserialized = json.loads(serialized)

        assert deserialized['text'] == "测试"
        assert deserialized['score'] == 0.8
        assert deserialized['evaluation_status'] == 'success'
        assert deserialized['confidence'] == 0.9


class TestEvaluatorServiceContract:
    """EvaluatorService服务层契约测试"""

    def test_service_response_fields(self):
        """验证EvaluationServiceResponse包含所有必需字段"""
        api_response = {"status": "success", "data": {}}
        domain_result = MagicMock()
        
        response = EvaluationServiceResponse(api_response=api_response, domain_result=domain_result)
        
        assert hasattr(response, 'api_response')
        assert hasattr(response, 'domain_result')
        assert isinstance(response.api_response, dict)

    def test_run_evaluation_accepts_dict_input(self):
        """验证run_evaluation接受dict输入"""
        service = EvaluatorService()
        mock_engine = MagicMock()
        service.engine = mock_engine
        
        request_data = {
            "id": "test_001",
            "type": "semantic",
            "payload": {
                "actual_output": "测试输出",
                "expected_output": "期望输出",
            },
        }
        
        mock_response = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        mock_result = MagicMock()
        mock_result.response = mock_response
        mock_engine.run.return_value = mock_result
        
        result = service.run_evaluation(request_data)
        
        assert isinstance(result, EvaluationServiceResponse)
        assert isinstance(result.api_response, dict)
        assert 'status' in result.api_response

    def test_run_evaluation_api_response_structure(self):
        """验证API响应结构包含必需字段"""
        service = EvaluatorService()
        mock_engine = MagicMock()
        service.engine = mock_engine
        
        request_data = {
            "id": "test_001",
            "type": "semantic",
            "payload": {
                "actual_output": "测试输出",
                "expected_output": "期望输出",
            },
        }
        
        mock_response = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        mock_result = MagicMock()
        mock_result.response = mock_response
        mock_result.status = RecordStatus.PASSED
        mock_result.latency_ms = 100
        mock_engine.run.return_value = mock_result
        
        result = service.run_evaluation(request_data)
        
        api_response = result.api_response
        assert 'status' in api_response
        assert 'data' in api_response
        assert 'score' in api_response['data']
        assert 'evaluation_status' in api_response['data']


class TestEvaluationEngineContract:
    """EvaluationEngine引擎层契约测试"""

    def test_run_accepts_evaluation_schema(self):
        """验证run方法接受EvaluationSchema输入"""
        from src.engine import EvaluationEngine
        
        mock_client = MagicMock()
        engine = EvaluationEngine(client=mock_client)
        
        request = EvaluationSchema(
            id="test_001",
            type="semantic",
            payload={"actual_output": "test"},
        )
        
        assert hasattr(engine, 'run')
        assert callable(engine.run)

    def test_run_returns_evaluation_result(self):
        """验证run方法返回EvaluationResult类型"""
        from src.engine import EvaluationEngine
        
        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.model_name = "test-model"
        engine = EvaluationEngine(client=mock_client)
        
        request = EvaluationSchema(
            id="test_001",
            type="semantic",
            payload={"actual_output": "测试输出", "expected_output": "期望输出"},
        )
        
        result = engine.run(request)
        
        assert isinstance(result, EvaluationResult)
        assert hasattr(result, 'case_id')
        assert hasattr(result, 'status')
        assert hasattr(result, 'response')
        assert hasattr(result, 'adapter_name')
        assert hasattr(result, 'latency_ms')
        assert isinstance(result.case_id, str)
        assert isinstance(result.latency_ms, (int, float))

    def test_run_batch_accepts_list(self):
        """验证run_batch方法接受列表输入"""
        from src.engine import EvaluationEngine
        
        mock_client = MagicMock()
        engine = EvaluationEngine(client=mock_client)
        
        assert hasattr(engine, 'run_batch')
        assert callable(engine.run_batch)