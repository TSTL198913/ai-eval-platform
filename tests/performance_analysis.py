import os
import sys
import time

os.environ["TESTING"] = "1"
os.environ["TEST_DATABASE_URL"] = "sqlite:///:memory:"

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def measure_import_time(module_name):
    """测量模块导入时间"""
    start = time.perf_counter()
    __import__(module_name)
    elapsed = time.perf_counter() - start
    print(f"  {module_name}: {elapsed:.3f}s")
    return elapsed


def main():
    print("=" * 60)
    print("性能分析：模块导入耗时")
    print("=" * 60)

    total_start = time.perf_counter()

    print("\n1. 基础模块导入：")
    import_start = time.perf_counter()
    import src.schemas.evaluation
    import src.schemas.schemas
    import src.domain.evaluators.evaluator_factory
    elapsed = time.perf_counter() - import_start
    print(f"  基础模块: {elapsed:.3f}s")

    print("\n2. 评估器导入（逐个）：")
    evaluator_modules = [
        "src.domain.evaluators.general",
        "src.domain.evaluators.finance",
        "src.domain.evaluators.code",
        "src.domain.evaluators.text",
        "src.domain.evaluators.semantic",
        "src.domain.evaluators.security",
        "src.domain.evaluators.llm_as_judge",
        "src.domain.evaluators.drift",
        "src.domain.evaluators.trajectory",
    ]
    eval_times = []
    for mod in evaluator_modules:
        t = measure_import_time(mod)
        eval_times.append(t)
    print(f"  评估器总计: {sum(eval_times):.3f}s")

    print("\n3. 引擎和服务导入：")
    engine_start = time.perf_counter()
    import src.engine
    import src.workers.tasks
    import src.workers.celery_app
    elapsed = time.perf_counter() - engine_start
    print(f"  引擎和服务: {elapsed:.3f}s")

    print("\n4. API服务器导入：")
    api_start = time.perf_counter()
    import src.api.server
    elapsed = time.perf_counter() - api_start
    print(f"  API服务器: {elapsed:.3f}s")

    total_elapsed = time.perf_counter() - total_start
    print("\n" + "=" * 60)
    print(f"总导入时间: {total_elapsed:.3f}s")
    print("=" * 60)


if __name__