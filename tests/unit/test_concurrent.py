"""并发场景测试"""

import threading
from concurrent.futures import ThreadPoolExecutor

from src.engine import EvaluationEngine
from src.schemas.evaluation import EvaluationSchema


class TestConcurrent:
    """并发评测场景测试"""

    def test_thread_concurrent(self, mock_llm):
        """测试多线程并发评测"""
        mock_llm.chat.return_value = 'test'
        engine = EvaluationEngine(mock_llm)
        results = []
        lock = threading.Lock()

        def run(cid):
            r = engine.run(EvaluationSchema(id=cid, type='general', payload={'user_input': 'test'}, metadata={}))
            with lock:
                results.append(r)

        threads = [threading.Thread(target=run, args=(str(i),)) for i in range(10)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        assert len(results) == 10

    def test_thread_pool(self, mock_llm):
        """测试线程池执行并发评测"""
        mock_llm.chat.return_value = 'test'
        engine = EvaluationEngine(mock_llm)

        def run(cid):
            return engine.run(EvaluationSchema(id=cid, type='general', payload={'user_input': 'test'}, metadata={}))

        with ThreadPoolExecutor(max_workers=5) as e:
            results = [e.submit(run, str(i)).result() for i in range(10)]

        assert len(results) == 10

    def test_concurrent_result_isolation(self, mock_llm):
        """测试并发结果隔离"""
        mock_llm.chat.return_value = 'test'
        engine = EvaluationEngine(mock_llm)
        results = []
        lock = threading.Lock()

        def run(cid):
            r = engine.run(EvaluationSchema(id=cid, type='general', payload={'user_input': cid}, metadata={}))
            with lock:
                results.append((cid, r))

        threads = [threading.Thread(target=run, args=(f'task_{i}',)) for i in range(5)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        assert len(results) == 5
        task_ids = [r[0] for r in results]
        assert sorted(task_ids) == [f'task_{i}' for i in range(5)]
