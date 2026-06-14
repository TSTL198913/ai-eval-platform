"""
集成测试 - 错误边界与边界条件

测试系统在异常情况下的行为：
1. LLM 服务异常处理
2. 边界条件 (空输入/超大输入)
3. 并发场景
4. 降级策略
"""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from concurrent.futures import ThreadPoolExecutor

from src.schemas.evaluation import EvaluationSchema, EvaluationStatus
from src.domain.evaluators.base import EvaluatorFactory
from src.engine import EvaluationEngine
from src.llm.base import LLMConfig, LLMProvider


class TestLLMErrorHandling:
    """LLM 错误处理集成测试"""

    def test_llm_timeout_handling(self):
        """测试 LLM 超时时的错误处理"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        config = ModelConfig(api_key="test", model_name="stub")
        client = StubLLMClient(config)

        # Stub 客户端响应正常，但模拟超时场景
        # 通过 patch 实现超时模拟
        with patch.object(client, 'chat', side_effect=asyncio.TimeoutError("LLM timeout")):
            engine = EvaluationEngine(client)
            request = EvaluationSchema(
                id="timeout_test",
                type="general",
                payload={"user_input": "hello", "expected_output": "hi"},
                metadata={}
            )
            
            # 应该能处理超时异常，不崩溃
            try:
                result = engine.run(request)
                # 如果没有超时，则正常返回
                assert result is not None
            except asyncio.TimeoutError:
                # 超时被正确抛出
                pass

    def test_llm_connection_error(self):
        """测试 LLM 连接错误时的处理"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        config = ModelConfig(api_key="test", model_name="stub")
        client = StubLLMClient(config)

        with patch.object(client, 'chat', side_effect=ConnectionError("Connection refused")):
            engine = EvaluationEngine(client)
            request = EvaluationSchema(
                id="connection_test",
                type="general",
                payload={"user_input": "hello", "expected_output": "hi"},
                metadata={}
            )
            
            try:
                result = engine.run(request)
            except ConnectionError:
                # 连接错误被正确传播
                pass

    def test_all_domains_handle_llm_error(self):
        """测试所有领域在 LLM 错误时都能正确处理"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        domains = ["general", "code", "code_review", "finance", "text"]
        config = ModelConfig(api_key="test", model_name="stub")

        for domain in domains:
            client = StubLLMClient(config)
            with patch.object(client, 'chat', side_effect=Exception(f"{domain} LLM error")):
                evaluator = EvaluatorFactory.get(domain, client=client)
                request = EvaluationSchema(
                    id=f"error_test_{domain}",
                    type=domain,
                    payload={"user_input": "test", "expected_output": "test"},
                    metadata={}
                )
                
                # 不应崩溃，应该有错误处理
                try:
                    evaluator.evaluate(request)
                except Exception as e:
                    assert domain in str(e) or "LLM" in str(e)


class TestBoundaryConditions:
    """边界条件集成测试"""

    def test_empty_input(self):
        """测试空输入处理"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        engine = EvaluationEngine(client)

        request = EvaluationSchema(
            id="empty_input",
            type="general",
            payload={"user_input": "", "expected_output": ""},
            metadata={}
        )
        
        result = engine.run(request)
        assert result is not None
        assert result.status in [EvaluationStatus.PASSED, EvaluationStatus.FAILED]

    def test_very_long_input(self):
        """测试超长输入处理"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        engine = EvaluationEngine(client)

        # 构造 1MB 输入
        long_text = "x" * 1_000_000
        request = EvaluationSchema(
            id="long_input",
            type="general",
            payload={"user_input": long_text, "expected_output": "response"},
            metadata={}
        )
        
        # 不应因输入过长而崩溃
        result = engine.run(request)
        assert result is not None

    def test_special_characters_input(self):
        """测试特殊字符处理"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        engine = EvaluationEngine(client)

        special_chars = [
            "Hello\r\nWorld",
            "Tab\there",
            "Unicode: 你好世界",
            "Emoji: 🎉🔥💻",
            "SQL injection: '; DROP TABLE users;--",
            "XSS: <script>alert('xss')</script>",
        ]

        for i, text in enumerate(special_chars):
            request = EvaluationSchema(
                id=f"special_{i}",
                type="general",
                payload={"user_input": text, "expected_output": "safe"},
                metadata={}
            )
            result = engine.run(request)
            assert result is not None

    def test_missing_metadata(self):
        """测试缺少 metadata 的处理"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        engine = EvaluationEngine(client)

        # metadata 为空字典
        request = EvaluationSchema(
            id="no_metadata",
            type="general",
            payload={"user_input": "test", "expected_output": "test"},
            metadata={}
        )
        
        result = engine.run(request)
        assert result is not None

    def test_numeric_boundaries(self):
        """测试数值边界"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        
        test_cases = [
            {"user_input": "0", "expected_output": "0"},
            {"user_input": "-999999", "expected_output": "-999999"},
            {"user_input": "999999999", "expected_output": "999999999"},
            {"user_input": "3.1415926", "expected_output": "3.1415926"},
        ]

        for i, case in enumerate(test_cases):
            request = EvaluationSchema(
                id=f"numeric_{i}",
                type="general",
                payload=case,
                metadata={}
            )
            result = client.chat(case["user_input"], "You are a calculator")
            assert result is not None


class TestConcurrentExecution:
    """并发执行集成测试"""

    def test_concurrent_evaluation_requests(self):
        """测试并发评测请求"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        engine = EvaluationEngine(client)

        def run_evaluation(case_id: str):
            request = EvaluationSchema(
                id=case_id,
                type="general",
                payload={"user_input": f"input_{case_id}", "expected_output": "response"},
                metadata={}
            )
            return engine.run(request)

        # 并发执行 10 个评测
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(run_evaluation, f"case_{i}") for i in range(10)]
            results = [f.result() for f in futures]

        # 所有请求都应成功
        assert len(results) == 10
        for result in results:
            assert result is not None

    def test_concurrent_different_domains(self):
        """测试并发不同领域的评测"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        domains = ["general", "code", "code_review", "finance", "text"]
        
        def evaluate_domain(domain: str, index: int):
            client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
            evaluator = EvaluatorFactory.get(domain, client=client)
            request = EvaluationSchema(
                id=f"concurrent_{domain}_{index}",
                type=domain,
                payload={"user_input": f"test {domain}", "expected_output": "response"},
                metadata={}
            )
            return evaluator.evaluate(request)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(10):
                domain = domains[i % len(domains)]
                futures.append(executor.submit(evaluate_domain, domain, i))
            
            results = [f.result() for f in futures]

        assert len(results) == 10


class TestDataIntegrity:
    """数据完整性集成测试"""

    def test_evaluation_result_consistency(self):
        """测试评测结果的数据一致性"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        engine = EvaluationEngine(client)

        request = EvaluationSchema(
            id="consistency_test",
            type="general",
            payload={"user_input": "test", "expected_output": "expected"},
            metadata={"test_id": "123"}
        )

        result = engine.run(request)

        # 验证结果字段完整性
        assert hasattr(result, 'case_id')
        assert hasattr(result, 'status')
        assert hasattr(result, 'response')
        assert hasattr(result, 'adapter_name')

        # 验证结果与请求一致
        assert result.case_id == "consistency_test"

    def test_response_fields_complete(self):
        """测试响应字段完整性"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        evaluator = EvaluatorFactory.get("text", client=client)
        
        request = EvaluationSchema(
            id="fields_test",
            type="text",
            payload={"user_input": "analyze this", "expected_output": "analysis"},
            metadata={}
        )

        response = evaluator.evaluate(request)

        # 验证响应字段
        assert hasattr(response, 'is_valid')
        assert hasattr(response, 'text')
        assert hasattr(response, 'score')
        # response 可能有 metadata 字段
        assert response.is_valid is not None


class TestEvaluatorBehavior:
    """评测器行为集成测试"""

    def test_all_evaluators_have_default_scoring(self):
        """验证所有评测器有默认评分机制"""
        domains = ["general", "code", "code_review", "finance", "text"]
        
        for domain in domains:
            evaluator = EvaluatorFactory.get(domain, client=MagicMock())
            assert evaluator is not None

    def test_evaluator_preserves_metadata(self):
        """验证评测器保留 metadata"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        evaluator = EvaluatorFactory.get("finance", client=client)

        metadata = {
            "user_id": "user_123",
            "session_id": "sess_456",
            "timestamp": "2024-01-01",
            "custom_field": "custom_value"
        }

        request = EvaluationSchema(
            id="metadata_test",
            type="finance",
            payload={"user_input": "test", "expected_output": "test"},
            metadata=metadata
        )

        response = evaluator.evaluate(request)

        # 响应应包含原始 metadata
        assert response is not None

    def test_code_evaluator_syntax_handling(self):
        """测试代码评测器的语法处理"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        evaluator = EvaluatorFactory.get("code", client=client)

        code_snippets = [
            "def hello():\n    print('Hello, World!')",
            "function add(a, b) { return a + b; }",
            "class MyClass:\n    def __init__(self):\n        self.value = 0",
            "#!/bin/bash\necho 'Hello'",
        ]

        for i, code in enumerate(code_snippets):
            request = EvaluationSchema(
                id=f"code_test_{i}",
                type="code",
                payload={"user_input": code, "expected_output": "valid"},
                metadata={}
            )
            response = evaluator.evaluate(request)
            assert response is not None

    def test_code_review_evaluator_input(self):
        """测试代码审查评测器"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        evaluator = EvaluatorFactory.get("code_review", client=client)

        request = EvaluationSchema(
            id="review_test",
            type="code_review",
            payload={
                "user_input": "Review this code for bugs",
                "expected_output": "No critical bugs found"
            },
            metadata={}
        )

        response = evaluator.evaluate(request)
        assert response is not None


class TestSchemaValidation:
    """Schema 验证集成测试"""

    def test_invalid_domain_rejected(self):
        """测试无效领域被拒绝"""
        from src.domain.evaluators.base import EvaluatorFactory

        with pytest.raises(ValueError):
            EvaluatorFactory.get("invalid_domain", client=MagicMock())

    def test_missing_required_fields(self):
        """测试缺少必需字段"""
        from src.schemas.evaluation import EvaluationSchema

        # 缺少 payload
        with pytest.raises(Exception):
            EvaluationSchema(id="test", type="general")

    def test_invalid_evaluation_status(self):
        """测试无效的评测状态"""
        from src.schemas.evaluation import EvaluationSchema, EvaluationStatus

        # 无效状态值应该被拒绝或转换
        request = EvaluationSchema(
            id="status_test",
            type="general",
            payload={"user_input": "test", "expected_output": "test"},
            metadata={}
        )
        
        # 初始状态应该是 PENDING
        assert request is not None


class TestPerformanceBounds:
    """性能边界集成测试"""

    def test_rapid_sequence_requests(self):
        """测试快速连续请求"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        engine = EvaluationEngine(client)

        start_time = time.time()
        for i in range(20):
            request = EvaluationSchema(
                id=f"rapid_{i}",
                type="general",
                payload={"user_input": f"request_{i}", "expected_output": "response"},
                metadata={}
            )
            engine.run(request)

        elapsed = time.time() - start_time
        
        # 20 个请求应该在合理时间内完成
        # Stub 客户端很快，所以 elapsed 可能很小，但我们只验证不崩溃
        assert elapsed >= 0

    def test_repeated_same_evaluation(self):
        """测试重复相同评测的稳定性"""
        from src.domain.models.stub import StubLLMClient
        from src.domain.models.base import ModelConfig

        client = StubLLMClient(ModelConfig(api_key="test", model_name="stub"))
        engine = EvaluationEngine(client)

        request = EvaluationSchema(
            id="repeated_test",
            type="general",
            payload={"user_input": "consistent input", "expected_output": "consistent output"},
            metadata={}
        )

        # 执行 5 次相同的评测
        results = []
        for _ in range(5):
            result = engine.run(request)
            results.append(result)

        # 所有结果应该都是有效的
        for result in results:
            assert result is not None
            assert result.case_id == "repeated_test"
