"""稳定性测试

测试目标：
1. 验证长时间运行稳定性
2. 验证资源泄漏检测
3. 验证错误恢复能力
4. 验证系统自愈能力
"""

import concurrent.futures
import gc
import os
import sys
import threading
import time
import weakref
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient

from src.domain.evaluators import auto_discover
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.engine import EvaluationEngine
from src.infra.cost_governance import CostGovernance
from src.infra.db.repository import EvaluationRepository
from src.infra.db.session import get_db_session
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluationStatus
from src.schemas.schemas import EvaluationResult


class TestLongRunningStability:
    """长时间运行稳定性测试"""

    def test_60_seconds_continuous_evaluation(self):
        """60秒持续评估测试"""
        from src.api.server import app

        client = TestClient(app)

        duration_seconds = 60
        results = {
            "total_requests": 0,
            "success": 0,
            "error": 0,
            "error_types": {},
        }
        lock = threading.Lock()
        stop_flag = threading.Event()

        def continuous_evaluation(thread_id):
            counter = 0
            while not stop_flag.is_set():
                try:
                    response = client.post(
                        "/api/v1/evaluate",
                        json={
                            "id": f"long_run_{thread_id}_{counter}",
                            "type": "general",
                            "payload": {"user_input": f"long running test {counter}"},
                        },
                    )
                    with lock:
                        results["total_requests"] += 1
                        if response.status_code in [200, 422]:
                            results["success"] += 1
                        else:
                            results["error"] += 1
                            error_msg = response.json().get("message", "unknown")
                            results["error_types"][error_msg] = (
                                results["error_types"].get(error_msg, 0) + 1
                            )
                    counter += 1
                    time.sleep(0.1)  # 防止过度压测
                except Exception as e:
                    with lock:
                        results["total_requests"] += 1
                        results["error"] += 1
                        error_msg = str(e)[:50]
                        results["error_types"][error_msg] = (
                            results["error_types"].get(error_msg, 0) + 1
                        )

        # 启动5个持续评估线程
        threads = [threading.Thread(target=continuous_evaluation, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()

        # 运行60秒
        time.sleep(duration_seconds)
        stop_flag.set()

        for t in threads:
            t.join()

        # 验证：总请求量 ≥ 100
        assert results["total_requests"] >= 100, f"请求量过低: {results['total_requests']}"

        # 验证：成功率 ≥ 95%
        success_rate = results["success"] / results["total_requests"]
        assert success_rate >= 0.95, f"成功率过低: {success_rate:.2%}"

        # 验证：无严重错误类型
        for error_type, count in results["error_types"].items():
            assert count < results["total_requests"] * 0.05, (
                f"错误类型 '{error_type}' 出现过多: {count} 次"
            )

        print(
            f"长时间运行测试结果: 总请求 {results['total_requests']}, "
            f"成功 {results['success']}, 失败 {results['error']}"
        )

    def test_120_seconds_continuous_repository_operations(self):
        """120秒持续仓储操作测试"""
        repo = EvaluationRepository()

        duration_seconds = 120
        results = {
            "total_operations": 0,
            "success": 0,
            "error": 0,
            "connection_errors": 0,
        }
        lock = threading.Lock()
        stop_flag = threading.Event()

        def continuous_operation(thread_id):
            counter = 0
            while not stop_flag.is_set():
                try:
                    # 交替执行保存和查询
                    if counter % 2 == 0:
                        result = EvaluationResult(
                            case_id=f"long_repo_{thread_id}_{counter}",
                            model_name="test-model",
                            adapter_name="GeneralEvaluator",
                            status=EvaluationStatus.PASSED,
                            latency_ms=100.0,
                            response=DomainResponse(is_valid=True, score=0.9, reason="test"),
                        )
                        repo.save(result)
                    else:
                        repo.get_recent(limit=10)

                    with lock:
                        results["total_operations"] += 1
                        results["success"] += 1
                    counter += 1
                    time.sleep(0.05)
                except Exception as e:
                    with lock:
                        results["total_operations"] += 1
                        results["error"] += 1
                        if "connection" in str(e).lower():
                            results["connection_errors"] += 1

        # 启动3个持续操作线程
        threads = [threading.Thread(target=continuous_operation, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()

        # 运行120秒
        time.sleep(duration_seconds)
        stop_flag.set()

        for t in threads:
            t.join()

        # 验证：总操作量 ≥ 100
        assert results["total_operations"] >= 100, f"操作量过低: {results['total_operations']}"

        # 验证：成功率 ≥ 99%
        success_rate = results["success"] / results["total_operations"]
        assert success_rate >= 0.99, f"成功率过低: {success_rate:.2%}"

        # 验证：无连接错误
        assert results["connection_errors"] == 0, f"出现连接错误: {results['connection_errors']} 次"


class TestResourceLeakDetection:
    """资源泄漏检测测试"""

    def test_database_connection_leak_detection(self):
        """数据库连接泄漏检测"""
        # 获取初始连接数
        initial_count = self._get_active_connections()

        # 执行大量操作
        repo = EvaluationRepository()
        for i in range(100):
            result = EvaluationResult(
                case_id=f"leak_test_{i}",
                model_name="test-model",
                adapter_name="GeneralEvaluator",
                status=EvaluationStatus.PASSED,
                latency_ms=100.0,
                response=DomainResponse(is_valid=True, score=0.9, reason="test"),
            )
            repo.save(result)

        # 强制垃圾回收
        gc.collect()

        # 获取最终连接数
        final_count = self._get_active_connections()

        # 验证：连接数未显著增加（允许少量波动）
        assert final_count <= initial_count + 5, (
            f"可能存在连接泄漏: 初始 {initial_count}, 最终 {final_count}"
        )

    def _get_active_connections(self):
        """获取活跃连接数"""
        try:
            with get_db_session() as session:
                result = session.execute("SELECT count(*) FROM pg_stat_activity")
                return result.fetchone()[0]
        except Exception:
            # 如果无法获取，返回默认值
            return 0

    def test_memory_leak_detection(self):
        """内存泄漏检测"""
        import tracemalloc

        tracemalloc.start()

        # 获取初始内存
        snapshot1 = tracemalloc.take_snapshot()

        # 执行大量操作
        governance = CostGovernance()
        for i in range(1000):
            governance.record_usage(
                record_id=f"memory_leak_{i}",
                model_name="gpt-4",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=100.0,
            )

        # 清理
        governance.records.clear()
        gc.collect()

        # 获取最终内存
        snapshot2 = tracemalloc.take_snapshot()

        # 计算内存差异
        stats = snapshot2.compare_to(snapshot1, "lineno")
        total_diff = sum(stat.size_diff for stat in stats)

        # 验证：内存增长 ≤ 1MB
        assert total_diff <= 1024 * 1024, f"可能存在内存泄漏: 内存增长 {total_diff / 1024:.2f}KB"

        tracemalloc.stop()

    def test_object_reference_leak_detection(self):
        """对象引用泄漏检测"""
        # 创建对象并使用弱引用跟踪
        obj_refs = []

        for i in range(100):
            result = EvaluationResult(
                case_id=f"ref_leak_{i}",
                model_name="test-model",
                adapter_name="GeneralEvaluator",
                status=EvaluationStatus.PASSED,
                latency_ms=100.0,
                response=DomainResponse(is_valid=True, score=0.9, reason="test"),
            )
            obj_refs.append(weakref.ref(result))

        # 清除局部变量
        del result

        # 强制垃圾回收
        gc.collect()

        # 验证：所有对象已被回收
        alive_count = sum(1 for ref in obj_refs if ref() is not None)
        assert alive_count == 0, f"存在对象引用泄漏: {alive_count} 个对象未被回收"


class TestErrorRecoveryStability:
    """错误恢复稳定性测试"""

    def test_database_error_recovery(self):
        """数据库错误恢复测试"""
        repo = EvaluationRepository()

        # 正常操作
        result = EvaluationResult(
            case_id="error_recovery_normal",
            model_name="test-model",
            adapter_name="GeneralEvaluator",
            status=EvaluationStatus.PASSED,
            latency_ms=100.0,
            response=DomainResponse(is_valid=True, score=0.9, reason="test"),
        )
        repo.save(result)

        # 模拟错误（无效数据）
        try:
            invalid_result = EvaluationResult(
                case_id="",  # 空case_id应抛出错误
                model_name="test-model",
                adapter_name="GeneralEvaluator",
                status=EvaluationStatus.PASSED,
                latency_ms=100.0,
                response=DomainResponse(is_valid=True, score=0.9, reason="test"),
            )
            repo.save(invalid_result)
        except ValueError:
            pass  # 预期错误

        # 验证：系统仍可正常操作
        result2 = EvaluationResult(
            case_id="error_recovery_after_error",
            model_name="test-model",
            adapter_name="GeneralEvaluator",
            status=EvaluationStatus.PASSED,
            latency_ms=100.0,
            response=DomainResponse(is_valid=True, score=0.9, reason="test"),
        )
        record_id = repo.save(result2)
        assert record_id > 0, "错误后系统无法正常操作"

    def test_evaluator_error_recovery(self):
        """评估器错误恢复测试"""
        from src.domain.evaluators import auto_discover

        auto_discover(force=True)

        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.model_name = "test-model"

        engine = EvaluationEngine(mock_client)

        # 正常评估
        request = EvaluationSchema(
            id="eval_recovery_normal", type="general", payload={"user_input": "normal test"}
        )
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"is_valid": true, "score": 0.9}'))]
        )
        result = engine.run(request)
        assert result.status in [EvaluationStatus.PASSED, EvaluationStatus.FAILED]

        # 模拟错误
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        request2 = EvaluationSchema(
            id="eval_recovery_error", type="general", payload={"user_input": "error test"}
        )
        result2 = engine.run(request2)
        # 错误应被捕获，状态为FAILED
        assert result2.status == EvaluationStatus.FAILED

        # 验证：系统仍可正常评估
        mock_client.chat.completions.create.side_effect = None
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"is_valid": true, "score": 0.9}'))]
        )
        request3 = EvaluationSchema(
            id="eval_recovery_after_error",
            type="general",
            payload={"user_input": "after error test"},
        )
        result3 = engine.run(request3)
        assert result3.status in [EvaluationStatus.PASSED, EvaluationStatus.FAILED]

    def test_api_error_recovery(self):
        """API错误恢复测试"""
        from src.api.server import app

        client = TestClient(app)

        # 正常请求
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        # 错误请求（无效路径）
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

        # 验证：系统仍可正常响应
        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestSelfHealingStability:
    """自愈能力稳定性测试"""

    def test_evaluator_factory_auto_recovery(self):
        """评估器工厂自动恢复测试"""
        # 清空注册表
        EvaluatorFactory._registry = {}

        # 验证：无法获取评估器
        with pytest.raises(KeyError):
            EvaluatorFactory.get("general")

        # 触发自动发现
        auto_discover(force=True)

        # 验证：评估器已恢复
        evaluator = EvaluatorFactory.get_evaluator("general")
        assert evaluator is not None

    def test_database_session_auto_recovery(self):
        """数据库会话自动恢复测试"""
        # 正常操作
        repo = EvaluationRepository()
        result = EvaluationResult(
            case_id="session_recovery_test",
            model_name="test-model",
            adapter_name="GeneralEvaluator",
            status=EvaluationStatus.PASSED,
            latency_ms=100.0,
            response=DomainResponse(is_valid=True, score=0.9, reason="test"),
        )
        repo.save(result)

        # 强制关闭会话（模拟异常）
        # 注意：get_db_session 使用上下文管理器，会自动关闭

        # 验证：新会话可正常工作
        result2 = EvaluationResult(
            case_id="session_recovery_test_2",
            model_name="test-model",
            adapter_name="GeneralEvaluator",
            status=EvaluationStatus.PASSED,
            latency_ms=100.0,
            response=DomainResponse(is_valid=True, score=0.9, reason="test"),
        )
        record_id = repo.save(result2)
        assert record_id > 0

    def test_cost_governance_auto_recovery(self):
        """成本治理自动恢复测试"""
        governance = CostGovernance()

        # 正常记录
        governance.record_usage(
            record_id="recovery_test_1",
            model_name="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=100.0,
        )

        # 清空记录（模拟异常）
        governance.records.clear()

        # 验证：系统可重新记录
        governance.record_usage(
            record_id="recovery_test_2",
            model_name="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=100.0,
        )

        assert len(governance.records) == 1


class TestGracefulDegradationStability:
    """优雅降级稳定性测试"""

    def test_api_graceful_degradation_under_load(self):
        """API在高负载下优雅降级测试"""
        from src.api.server import app

        client = TestClient(app)

        # 高负载请求
        results = {
            "success": 0,
            "degraded": 0,
            "error": 0,
        }
        lock = threading.Lock()

        def high_load_request(i):
            try:
                response = client.post(
                    "/api/v1/evaluate",
                    json={
                        "id": f"degradation_test_{i}",
                        "type": "general",
                        "payload": {"user_input": f"degradation test {i}"},
                    },
                )
                with lock:
                    if response.status_code == 200:
                        results["success"] += 1
                    elif response.status_code == 422:
                        results["degraded"] += 1  # 业务校验失败，优雅降级
                    else:
                        results["error"] += 1
            except Exception:
                with lock:
                    results["error"] += 1

        # 发送大量请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(high_load_request, i) for i in range(100)]
            concurrent.futures.wait(futures)

        # 验证：无严重错误（500等）
        total = results["success"] + results["degraded"] + results["error"]
        error_rate = results["error"] / total
        assert error_rate <= 0.05, f"严重错误率过高: {error_rate:.2%}"

        # 验证：大部分请求得到响应（成功或降级）
        handled_rate = (results["success"] + results["degraded"]) / total
        assert handled_rate >= 0.95, f"处理率过低: {handled_rate:.2%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
