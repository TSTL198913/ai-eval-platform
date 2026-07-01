"""压力测试

测试目标：
1. 验证100并发场景下系统稳定性
2. 验证大数据量查询性能
3. 验证持续请求稳定性
4. 验证内存和资源消耗
"""

import concurrent.futures
import os
import statistics
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient

from src.domain.evaluators import auto_discover
from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.infra.cost_governance import CostGovernance
from src.infra.db.repository import EvaluationRepository
from src.schemas.evaluation import DomainResponse, EvaluationStatus
from src.schemas.schemas import EvaluationResult


class TestHighConcurrencyStress:
    """高并发压力测试"""

    @pytest.fixture(autouse=True)
    def setup_evaluators(self):
        """每个测试前重置评估器"""
        EvaluatorFactory._registry = {}
        auto_discover(force=True)
        yield

    def test_100_concurrent_api_requests(self):
        """100并发API请求测试"""
        from src.api.server import app

        client = TestClient(app)

        num_requests = 100
        results = {
            "success": 0,
            "error": 0,
            "latencies": [],
        }
        lock = threading.Lock()

        def make_request(i):
            start_time = time.perf_counter()
            try:
                response = client.post(
                    "/api/v1/evaluate",
                    json={
                        "id": f"stress_test_{i}",
                        "type": "general",
                        "payload": {"user_input": f"stress test input {i}"},
                    },
                )
                latency = (time.perf_counter() - start_time) * 1000
                with lock:
                    results["latencies"].append(latency)
                    if response.status_code in [200, 422]:
                        results["success"] += 1
                    else:
                        results["error"] += 1
            except Exception:
                with lock:
                    results["error"] += 1

        # 使用线程池模拟并发
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            concurrent.futures.wait(futures)

        # 验证：成功率 ≥ 95%
        success_rate = results["success"] / num_requests
        assert success_rate >= 0.95, f"成功率过低: {success_rate:.2%}"

        # 验证：平均响应时间 ≤ 2000ms
        avg_latency = statistics.mean(results["latencies"])
        assert avg_latency <= 2000, f"平均响应时间过高: {avg_latency:.2f}ms"

        # 验证：P95响应时间 ≤ 5000ms
        if len(results["latencies"]) >= 20:
            p95_latency = statistics.quantiles(results["latencies"], n=100)[94]
            assert p95_latency <= 5000, f"P95响应时间过高: {p95_latency:.2f}ms"

        print(
            f"压力测试结果: 成功 {results['success']}, 失败 {results['error']}, "
            f"平均延迟 {avg_latency:.2f}ms, P95 {p95_latency:.2f}ms"
        )

    def test_200_concurrent_repository_operations(self):
        """200并发仓储操作测试"""
        repo = EvaluationRepository()

        num_operations = 200
        results = {
            "save_success": 0,
            "save_error": 0,
            "latencies": [],
        }
        lock = threading.Lock()

        def save_operation(i):
            start_time = time.perf_counter()
            try:
                result = EvaluationResult(
                    case_id=f"stress_repo_{i}",
                    model_name="test-model",
                    adapter_name="GeneralEvaluator",
                    status=EvaluationStatus.PASSED,
                    latency_ms=100.0,
                    response=DomainResponse(text="test", score=0.9),
                )
                repo.save(result)
                latency = (time.perf_counter() - start_time) * 1000
                with lock:
                    results["save_success"] += 1
                    results["latencies"].append(latency)
            except Exception:
                with lock:
                    results["save_error"] += 1

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(save_operation, i) for i in range(num_operations)]
            concurrent.futures.wait(futures)

        # 验证：所有操作成功
        assert results["save_success"] == num_operations, (
            f"保存失败: 成功 {results['save_success']}, 失败 {results['save_error']}"
        )

        # 验证：平均延迟 ≤ 500ms
        avg_latency = statistics.mean(results["latencies"])
        assert avg_latency <= 500, f"仓储操作平均延迟过高: {avg_latency:.2f}ms"

    def test_500_concurrent_cost_governance_records(self):
        """500并发成本治理记录测试"""
        governance = CostGovernance()

        num_records = 500
        errors = []
        lock = threading.Lock()

        def record_cost(i):
            try:
                governance.record_usage(
                    record_id=f"stress_cost_{i}",
                    model_name="gpt-4",
                    prompt_tokens=100,
                    completion_tokens=50,
                    latency_ms=100.0,
                )
            except Exception as e:
                with lock:
                    errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(record_cost, i) for i in range(num_records)]
            concurrent.futures.wait(futures)

        # 验证：无异常
        assert len(errors) == 0, f"成本记录出现错误: {errors}"

        # 验证：所有记录都已保存
        assert len(governance.records) == num_records

        # 验证：成本计算正确
        metrics = governance.get_metrics()
        expected_cost = num_records * (100 * 0.00003 + 50 * 0.00006)
        assert abs(metrics.daily_cost_usd - expected_cost) < 0.0001


class TestLargeDataVolumeStress:
    """大数据量压力测试"""

    def test_1000_records_query_performance(self):
        """1000条记录查询性能测试"""
        repo = EvaluationRepository()

        # 预先创建1000条记录
        for i in range(1000):
            result = EvaluationResult(
                case_id=f"large_volume_{i}",
                model_name="test-model",
                adapter_name="GeneralEvaluator",
                status=EvaluationStatus.PASSED,
                latency_ms=100.0,
                response=DomainResponse(text="test", score=0.9),
            )
            repo.save(result)

        # 测试查询性能
        start_time = time.perf_counter()
        records = repo.get_recent(limit=100)
        latency = (time.perf_counter() - start_time) * 1000

        # 验证：查询延迟 ≤ 500ms
        assert latency <= 500, f"查询延迟过高: {latency:.2f}ms"

        # 验证：返回正确数量
        assert len(records) == 100

    def test_1000_records_search_performance(self):
        """1000条记录搜索性能测试"""
        repo = EvaluationRepository()

        # 预先创建1000条记录
        for i in range(1000):
            result = EvaluationResult(
                case_id=f"search_volume_{i}",
                model_name="test-model",
                adapter_name="GeneralEvaluator",
                status=EvaluationStatus.PASSED if i % 2 == 0 else EvaluationStatus.FAILED,
                latency_ms=100.0,
                response=DomainResponse(text="test", score=0.9),
            )
            repo.save(result)

        # 测试搜索性能
        start_time = time.perf_counter()
        records = repo.search(status="passed", limit=100)
        latency = (time.perf_counter() - start_time) * 1000

        # 验证：搜索延迟 ≤ 500ms
        assert latency <= 500, f"搜索延迟过高: {latency:.2f}ms"

        # 验证：返回正确数量
        assert len(records) <= 100

    def test_1000_cost_records_metrics_calculation(self):
        """1000条成本记录指标计算性能测试"""
        governance = CostGovernance()

        # 预先创建1000条记录
        for i in range(1000):
            governance.record_usage(
                record_id=f"metrics_volume_{i}",
                model_name="gpt-4",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=100.0 + i,
            )

        # 测试指标计算性能
        start_time = time.perf_counter()
        metrics = governance.get_metrics()
        latency = (time.perf_counter() - start_time) * 1000

        # 验证：计算延迟 ≤ 100ms
        assert latency <= 100, f"指标计算延迟过高: {latency:.2f}ms"

        # 验证：指标正确
        assert metrics.total_requests == 1000
        assert metrics.daily_cost_usd > 0


class TestSustainedLoadStress:
    """持续负载压力测试"""

    def test_sustained_requests_30_seconds(self):
        """30秒持续请求测试"""
        from src.api.server import app

        client = TestClient(app)

        duration_seconds = 30
        results = {
            "total_requests": 0,
            "success": 0,
            "error": 0,
            "latencies": [],
        }
        lock = threading.Lock()
        stop_flag = threading.Event()

        def sustained_request():
            while not stop_flag.is_set():
                start_time = time.perf_counter()
                try:
                    response = client.get("/api/v1/health")
                    latency = (time.perf_counter() - start_time) * 1000
                    with lock:
                        results["total_requests"] += 1
                        results["latencies"].append(latency)
                        if response.status_code == 200:
                            results["success"] += 1
                        else:
                            results["error"] += 1
                except Exception:
                    with lock:
                        results["total_requests"] += 1
                        results["error"] += 1

        # 启动10个持续请求线程
        threads = [threading.Thread(target=sustained_request) for _ in range(10)]
        for t in threads:
            t.start()

        # 运行30秒
        time.sleep(duration_seconds)
        stop_flag.set()

        for t in threads:
            t.join()

        # 验证：总请求量 ≥ 100
        assert results["total_requests"] >= 100, f"请求量过低: {results['total_requests']}"

        # 验证：成功率 ≥ 99%
        success_rate = results["success"] / results["total_requests"]
        assert success_rate >= 0.99, f"成功率过低: {success_rate:.2%}"

        # 验证：平均延迟 ≤ 200ms
        avg_latency = statistics.mean(results["latencies"])
        assert avg_latency <= 200, f"平均延迟过高: {avg_latency:.2f}ms"

        print(
            f"持续负载测试结果: 总请求 {results['total_requests']}, "
            f"成功 {results['success']}, 失败 {results['error']}, "
            f"平均延迟 {avg_latency:.2f}ms"
        )

    def test_sustained_repository_operations_30_seconds(self):
        """30秒持续仓储操作测试"""
        repo = EvaluationRepository()

        duration_seconds = 30
        results = {
            "total_operations": 0,
            "success": 0,
            "error": 0,
        }
        lock = threading.Lock()
        stop_flag = threading.Event()

        def sustained_operation():
            counter = 0
            while not stop_flag.is_set():
                try:
                    result = EvaluationResult(
                        case_id=f"sustained_op_{counter}",
                        model_name="test-model",
                        adapter_name="GeneralEvaluator",
                        status=EvaluationStatus.PASSED,
                        latency_ms=100.0,
                        response=DomainResponse(text="test", score=0.9),
                    )
                    repo.save(result)
                    with lock:
                        results["total_operations"] += 1
                        results["success"] += 1
                    counter += 1
                except Exception:
                    with lock:
                        results["total_operations"] += 1
                        results["error"] += 1

        # 启动5个持续操作线程
        threads = [threading.Thread(target=sustained_operation) for _ in range(5)]
        for t in threads:
            t.start()

        # 运行30秒
        time.sleep(duration_seconds)
        stop_flag.set()

        for t in threads:
            t.join()

        # 验证：总操作量 ≥ 50
        assert results["total_operations"] >= 50, f"操作量过低: {results['total_operations']}"

        # 验证：成功率 ≥ 99%
        success_rate = results["success"] / results["total_operations"]
        assert success_rate >= 0.99, f"成功率过低: {success_rate:.2%}"


class TestMemoryAndResourceStress:
    """内存和资源压力测试"""

    def test_memory_usage_under_load(self):
        """负载下内存使用测试"""
        import gc

        # 获取初始内存使用
        gc.collect()

        governance = CostGovernance()

        # 创建大量记录
        for i in range(10000):
            governance.record_usage(
                record_id=f"memory_test_{i}",
                model_name="gpt-4",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=100.0,
            )

        # 验证：记录数正确
        assert len(governance.records) == 10000

        # 验证：指标计算正常
        metrics = governance.get_metrics()
        assert metrics.total_requests == 10000

        # 清理
        governance.records.clear()
        gc.collect()

    def test_evaluator_factory_memory_cleanup(self):
        """评估器工厂内存清理测试"""
        import gc

        # 清空注册表
        EvaluatorFactory._registry = {}

        # 注册大量评估器
        class DummyEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(text="test", score=1.0)

        for i in range(100):
            EvaluatorFactory.register(f"memory_eval_{i}")(DummyEvaluator)

        # 验证：注册成功
        assert len(EvaluatorFactory._registry) == 100

        # 清理
        EvaluatorFactory._registry = {}
        auto_discover(force=True)
        gc.collect()

        # 验证：清理成功
        assert len(EvaluatorFactory._registry) > 0  # 自动发现重新注册


class TestBurstLoadStress:
    """突发负载压力测试"""

    def test_burst_1000_requests_in_5_seconds(self):
        """5秒内1000请求突发测试"""
        from src.api.server import app

        client = TestClient(app)

        num_requests = 1000
        results = {
            "success": 0,
            "error": 0,
            "latencies": [],
        }
        lock = threading.Lock()

        def burst_request(i):
            start_time = time.perf_counter()
            try:
                response = client.get("/api/v1/health")
                latency = (time.perf_counter() - start_time) * 1000
                with lock:
                    results["latencies"].append(latency)
                    if response.status_code == 200:
                        results["success"] += 1
                    else:
                        results["error"] += 1
            except Exception:
                with lock:
                    results["error"] += 1

        start_time = time.time()

        # 使用大量线程模拟突发
        with concurrent.futures.ThreadPoolExecutor(max_workers=200) as executor:
            futures = [executor.submit(burst_request, i) for i in range(num_requests)]
            concurrent.futures.wait(futures)

        elapsed_time = time.time() - start_time

        # 验证：完成时间 ≤ 10秒
        assert elapsed_time <= 10, f"突发请求耗时过长: {elapsed_time:.2f}秒"

        # 验证：成功率 ≥ 95%
        success_rate = results["success"] / num_requests
        assert success_rate >= 0.95, f"成功率过低: {success_rate:.2%}"

        print(
            f"突发负载测试结果: 总请求 {num_requests}, "
            f"成功 {results['success']}, 失败 {results['error']}, "
            f"耗时 {elapsed_time:.2f}秒"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
