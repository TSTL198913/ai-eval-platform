"""Performance tests"""

import time
import statistics
import pytest
from concurrent.futures import ThreadPoolExecutor

from src.engine import EvaluationEngine
from src.schemas.evaluation import EvaluationSchema


class TestPerformanceBaseline:
    @pytest.mark.slow
    def test_engine_latency(self, mock_llm):
        mock_llm.chat.return_value = "test"
        engine = EvaluationEngine(mock_llm)
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            engine.run(EvaluationSchema(id="p1", type="general", payload={"user_input": "test"}, metadata={}))
            latencies.append(time.perf_counter() - start)
        avg = statistics.mean(latencies)
        assert avg < 0.1, f"Latency {avg:.4f}s"

    @pytest.mark.slow
    def test_engine_throughput(self, mock_llm):
        mock_llm.chat.return_value = "test"
        engine = EvaluationEngine(mock_llm)
        start = time.perf_counter()
        for i in range(50):
            engine.run(EvaluationSchema(id=f"th_{i}", type="general", payload={"user_input": "test"}, metadata={}))
        elapsed = time.perf_counter() - start
        throughput = 50 / elapsed
        assert throughput > 50, f"Throughput {throughput:.1f} req/s"

    @pytest.mark.slow
    def test_concurrent_throughput(self, mock_llm):
        mock_llm.chat.return_value = "test"
        engine = EvaluationEngine(mock_llm)
        def run(cid):
            return engine.run(EvaluationSchema(id=cid, type="general", payload={"user_input": "test"}, metadata={}))
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as e:
            results = [e.submit(run, str(i)).result() for i in range(20)]
        elapsed = time.perf_counter() - start
        throughput = 20 / elapsed
        assert throughput > 30, f"Concurrent {throughput:.1f} req/s"
        assert len(results) == 20
