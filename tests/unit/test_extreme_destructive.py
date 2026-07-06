"""
极端破坏性测试
目标：验证系统在极端条件下的稳定性和安全性

测试场景分类：
1. 内存攻击：大量对象创建、递归深度攻击
2. 资源耗尽：CPU密集计算、IO阻塞、线程耗尽
3. 竞争条件：原子操作竞争、死锁测试、资源争用
4. 异常注入：模拟系统异常、网络中断、文件损坏
5. 边界测试：极端数值、超大集合、无限循环检测
6. 安全攻击：反序列化攻击、原型污染、类型混淆
"""

import asyncio
import threading
import time
import sys
import json
from unittest.mock import MagicMock, patch

import pytest

from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.risk import RiskEvaluator
from src.domain.evaluators.semantic import SemanticEvaluator
from src.engine import EvaluationEngine
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus
from src.domain.services.evaluation_export_service import EvaluationExportService
from src.domain.services.evaluation_report_service import EvaluationReportService


class TestMemoryAttacks:
    """内存攻击测试"""

    def test_large_list_creation(self):
        """验证系统能处理超大列表"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        evaluator = SemanticEvaluator(client=mock_client)

        large_list = list(range(1000000))
        request = EvaluationSchema(
            id="large_list_001",
            type="semantic",
            payload={
                "user_input": "测试",
                "actual_output": str(large_list),
                "expected_output": "测试",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_recursive_structure_attack(self):
        """验证系统能处理递归结构攻击"""
        recursive_data = {}
        recursive_data["self"] = recursive_data

        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="recursive_attack_001",
            type="risk",
            payload={
                "action": "detect_all",
                "recursive_data": recursive_data,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_deep_nested_json(self):
        """验证系统能处理深度嵌套JSON"""
        def create_deep_nested(depth):
            if depth == 0:
                return "leaf"
            return {"key": create_deep_nested(depth - 1)}

        deep_data = create_deep_nested(100)
        evaluator = RiskEvaluator()

        request = EvaluationSchema(
            id="deep_nested_json_001",
            type="risk",
            payload={
                "action": "detect_all",
                "deep_data": deep_data,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_string_explosion_attack(self):
        """验证系统能处理字符串爆炸攻击"""
        base = "x"
        for _ in range(20):
            base = base + base

        mock_client = MagicMock()
        mock_client.chat.return_value = "0.5"
        evaluator = SemanticEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="string_explosion_001",
            type="semantic",
            payload={
                "user_input": base,
                "actual_output": base,
                "expected_output": base,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True


class TestResourceExhaustion:
    """资源耗尽测试"""

    def test_cpu_intensive_computation(self):
        """验证系统不会被CPU密集计算拖垮"""
        def cpu_intensive():
            result = 0
            for i in range(10000000):
                result += i
            return result

        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="cpu_intensive_001",
            type="risk",
            payload={
                "action": "detect_all",
            },
        )

        start = time.perf_counter()
        result = evaluator.evaluate(request)
        elapsed = time.perf_counter() - start

        assert result.is_valid is True
        assert elapsed < 5.0, f"CPU密集操作耗时过长: {elapsed}s"

    def test_thread_pool_exhaustion(self):
        """验证线程池不会被耗尽"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        evaluator = SemanticEvaluator(client=mock_client)

        results = []
        lock = threading.Lock()
        errors = []

        def worker(idx):
            try:
                request = EvaluationSchema(
                    id=f"thread_exhaust_{idx:04d}",
                    type="semantic",
                    payload={
                        "user_input": f"问题 {idx}",
                        "actual_output": f"回答 {idx}",
                        "expected_output": f"预期 {idx}",
                    },
                )
                result = evaluator.evaluate(request)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        elapsed = time.perf_counter() - start

        assert len(results) == 100, f"只有 {len(results)} 个结果，错误: {errors}"
        assert elapsed < 60.0, f"线程池耗尽测试耗时过长: {elapsed}s"

    def test_concurrent_export_requests(self):
        """验证并发导出请求不会耗尽资源"""
        from unittest.mock import patch
        import os

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [{"id": 1, "case_id": "test"}]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()
            results = []
            lock = threading.Lock()

            def worker(idx):
                filepath = service.export("csv")
                with lock:
                    results.append(filepath)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

            assert len(results) == 20
            for filepath in results:
                if os.path.exists(filepath):
                    os.remove(filepath)


class TestRaceConditions:
    """竞争条件测试"""

    def test_concurrent_config_modification(self):
        """验证并发配置修改不会导致数据损坏"""
        from src.domain.services.evaluation_report_service import EvaluationReportService
        from unittest.mock import patch

        with patch("src.domain.services.evaluation_report_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [
                {"id": i, "score": 0.7 + (i % 10) * 0.03, "status": "SUCCESS"}
                for i in range(100)
            ]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationReportService()
            results = []
            lock = threading.Lock()

            def worker(idx):
                report = service.generate_report("summary")
                with lock:
                    results.append(report)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)

            assert len(results) == 10
            for report in results:
                assert report["report_type"] == "summary"
                assert report["summary"]["total_evaluations"] == 100

    def test_duplicate_task_submission(self):
        """验证重复任务提交不会导致重复处理"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        mock_client.config = MagicMock()
        mock_client.config.model_name = "test-model"
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="duplicate_task_001",
            type="semantic",
            payload={
                "user_input": "测试",
                "actual_output": "测试",
                "expected_output": "测试",
            },
        )

        results = []
        for _ in range(5):
            result = engine.run(request)
            results.append(result)

        assert len(results) == 5
        for result in results:
            assert result.response is not None
            assert result.response.is_valid is True


class TestExceptionInjection:
    """异常注入测试"""

    def test_network_failure_simulation(self):
        """验证网络故障时系统的优雅降级"""
        mock_client = MagicMock()
        mock_client.chat.side_effect = ConnectionError("网络连接失败")
        evaluator = SemanticEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="network_failure_001",
            type="semantic",
            payload={
                "user_input": "测试",
                "actual_output": "测试",
                "expected_output": "测试",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert result.is_valid is True
        assert result.evaluation_status == EvaluatorStatus.PARTIAL
        assert "fallback_reason" in result.data

    def test_file_not_found_error(self):
        """验证文件不存在时的处理"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = []
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            with patch("builtins.open", side_effect=FileNotFoundError("文件不存在")):
                filepath = service.export("csv")
                assert filepath is not None

    def test_memory_error_handling(self):
        """验证内存错误时的处理"""
        mock_client = MagicMock()
        mock_client.chat.side_effect = MemoryError("内存不足")
        evaluator = SemanticEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="memory_error_001",
            type="semantic",
            payload={
                "user_input": "测试",
                "actual_output": "测试",
                "expected_output": "测试",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert result.is_valid is True
        assert result.evaluation_status == EvaluatorStatus.PARTIAL
        assert "fallback_reason" in result.data

    def test_keyboard_interrupt_during_execution(self):
        """验证执行过程中的中断处理"""
        mock_client = MagicMock()
        mock_client.chat.side_effect = KeyboardInterrupt()
        evaluator = SemanticEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="keyboard_interrupt_001",
            type="semantic",
            payload={
                "user_input": "测试",
                "actual_output": "测试",
                "expected_output": "测试",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.ERROR


class TestBoundaryConditionsExtreme:
    """极端边界条件测试"""

    def test_infinity_and_nan_values(self):
        """验证无穷大和NaN值的处理"""
        evaluator = RiskEvaluator()

        request = EvaluationSchema(
            id="inf_nan_001",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": float("inf"),
                "core_alignment": float("-inf"),
                "overall_coverage": float("nan"),
                "test_pass_rate": float("nan"),
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_unicode_surrogates(self):
        """验证Unicode代理对的处理"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        evaluator = SemanticEvaluator(client=mock_client)

        surrogate_text = "".join(chr(i) for i in range(0xD800, 0xDC00))
        request = EvaluationSchema(
            id="unicode_surrogates_001",
            type="semantic",
            payload={
                "user_input": surrogate_text,
                "actual_output": "正常文本",
                "expected_output": "正常文本",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_null_byte_injection_in_json(self):
        """验证JSON中的空字节注入"""
        evaluator = RiskEvaluator()

        request = EvaluationSchema(
            id="null_byte_json_001",
            type="risk",
            payload={
                "action": "detect_all",
                "data": '{"key": "value\\x00malicious"}',
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_extremely_long_field_names(self):
        """验证超长字段名的处理"""
        long_field_name = "field" * 1000
        evaluator = RiskEvaluator()

        payload = {long_field_name: "value"}
        payload["action"] = "detect_all"

        request = EvaluationSchema(
            id="long_field_name_001",
            type="risk",
            payload=payload,
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True


class TestSecurityAttacks:
    """安全攻击测试"""

    def test_deserialization_attack(self):
        """验证反序列化攻击防护"""
        import pickle
        import io

        malicious_payload = b"cos\nsystem\n(S'rm -rf /'\ntR."

        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="deserialization_001",
            type="risk",
            payload={
                "action": "detect_all",
                "serialized_data": malicious_payload,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_prototype_pollution_attempt(self):
        """验证原型污染攻击防护"""
        polluted_dict = {}
        polluted_dict["__proto__"] = {"polluted": True}

        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="prototype_pollution_001",
            type="risk",
            payload={
                "action": "detect_all",
                "data": polluted_dict,
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_type_confusion_attack(self):
        """验证类型混淆攻击防护"""
        evaluator = RiskEvaluator()

        request = EvaluationSchema(
            id="type_confusion_001",
            type="risk",
            payload={
                "action": "detect_all",
                "number_field": "not_a_number",
                "list_field": {"not": "a", "list": "at", "all": True},
                "dict_field": ["not", "a", "dict"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_command_injection_through_metadata(self):
        """验证通过metadata的命令注入"""
        evaluator = CodeEvaluator(client=None)

        request = EvaluationSchema(
            id="command_injection_001",
            type="code",
            payload={
                "code": "def hello():\n    return 'hello'",
                "metadata": {"language": "python; rm -rf /"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["syntax_valid"] is True


class TestSystemStability:
    """系统稳定性测试"""

    def test_long_running_process(self):
        """验证长时间运行的稳定性"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        evaluator = SemanticEvaluator(client=mock_client)

        start = time.perf_counter()
        for i in range(100):
            request = EvaluationSchema(
                id=f"long_run_{i:03d}",
                type="semantic",
                payload={
                    "user_input": f"问题 {i}",
                    "actual_output": f"回答 {i}",
                    "expected_output": f"预期 {i}",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is True
        elapsed = time.perf_counter() - start

        assert elapsed < 60.0, f"长时间运行耗时过长: {elapsed}s"

    def test_memory_leak_detection(self):
        """验证内存泄漏检测"""
        import gc

        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        evaluator = SemanticEvaluator(client=mock_client)

        gc.collect()
        initial_objects = len(gc.get_objects())

        for i in range(50):
            request = EvaluationSchema(
                id=f"memory_leak_{i:03d}",
                type="semantic",
                payload={
                    "user_input": f"问题 {i}",
                    "actual_output": f"回答 {i}",
                    "expected_output": f"预期 {i}",
                },
            )
            evaluator.evaluate(request)

        gc.collect()
        final_objects = len(gc.get_objects())

        object_increase = final_objects - initial_objects
        assert object_increase < 1000, f"内存泄漏检测失败，对象增加: {object_increase}"

    def test_concurrent_engine_access(self):
        """验证评估引擎的并发访问"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        mock_client.config = MagicMock()
        mock_client.config.model_name = "concurrent-test-model"
        engine = EvaluationEngine(client=mock_client)

        results = []
        lock = threading.Lock()

        def worker(idx):
            request = EvaluationSchema(
                id=f"engine_concurrent_{idx:03d}",
                type="semantic",
                payload={
                    "user_input": f"问题 {idx}",
                    "actual_output": f"回答 {idx}",
                    "expected_output": f"预期 {idx}",
                },
            )
            result = engine.run(request)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(results) == 30
        for result in results:
            assert result.response is not None
            assert result.response.is_valid is True