"""测试 infra/logger.py 和 infra/tracing.py"""

import uuid

from src.infra.tracing import generate_trace_id, trace_id_var


class TestTraceIdVar:
    """测试 Trace ID 上下文变量"""

    def test_default_value(self):
        assert trace_id_var.get() == "system"

    def test_set_and_get(self):
        token = trace_id_var.set("test-trace-123")
        assert trace_id_var.get() == "test-trace-123"
        trace_id_var.reset(token)

    def test_context_isolation(self):
        """测试上下文隔离"""
        import concurrent.futures

        results = []

        def worker(value):
            token = trace_id_var.set(value)
            result = trace_id_var.get()
            trace_id_var.reset(token)
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker, "thread-1")
            f2 = executor.submit(worker, "thread-2")
            results.append(f1.result())
            results.append(f2.result())

        assert "thread-1" in results
        assert "thread-2" in results


class TestGenerateTraceId:
    """测试 Trace ID 生成"""

    def test_generates_string(self):
        trace_id = generate_trace_id()
        assert isinstance(trace_id, str)

    def test_generates_valid_uuid_prefix(self):
        trace_id = generate_trace_id()
        assert len(trace_id) == 8
        # 验证是有效的 UUID 前缀
        full_uuid = f"{trace_id}-0000-0000-0000-000000000000"
        uuid.UUID(full_uuid)

    def test_generates_unique_ids(self):
        ids = [generate_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestLoggerModule:
    """测试 logger 模块"""

    def test_logger_import(self):
        from src.infra import logger

        assert logger is not None

    def test_logger_has_trace_id(self):
        from src.infra import logger
        from src.infra.tracing import trace_id_var

        token = trace_id_var.set("test-123")
        try:
            assert logger.logger is not None
        finally:
            trace_id_var.reset(token)
