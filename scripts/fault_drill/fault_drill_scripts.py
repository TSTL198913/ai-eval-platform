#!/usr/bin/env python3
"""
AI Eval Platform 故障演练脚本

用法:
    python fault_drill_scripts.py --scenario <场景名>
    python fault_drill_scripts.py --list

支持的场景:
    - llm_failure: LLM服务不可用
    - db_connection_pool: 数据库连接池耗尽
    - redis_failure: Redis缓存故障
    - network_delay: 网络延迟增加
    - evaluator_registration: 评估器注册失败

注意: 本脚本仅用于测试环境，请勿在生产环境使用！
"""

import argparse
import json
import time
import requests
import threading
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

API_BASE_URL = "http://localhost:8000"


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_status(message, status="INFO"):
    print(f"[{status}] {message}")


def get_baseline_metrics():
    """获取基线指标"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/metrics")
        return response.text
    except Exception as e:
        print_status(f"获取基线指标失败: {e}", "ERROR")
        return None


def run_evaluation_test(iterations=10):
    """运行评估测试"""
    success_count = 0
    error_count = 0
    total_latency = 0

    for i in range(iterations):
        start_time = time.time()
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/v1/evaluate",
                json={
                    "id": f"test_{i}",
                    "type": "general",
                    "payload": {"user_input": "测试问题"},
                },
            )
            latency = time.time() - start_time
            total_latency += latency

            if response.status_code == 200:
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            error_count += 1
            latency = time.time() - start_time
            total_latency += latency

    avg_latency = total_latency / iterations if iterations > 0 else 0
    success_rate = success_count / iterations * 100 if iterations > 0 else 0

    return {
        "success_count": success_count,
        "error_count": error_count,
        "success_rate": success_rate,
        "avg_latency": avg_latency,
    }


class LLMSimulator:
    """LLM服务模拟器"""

    def __init__(self):
        self._is_healthy = True

    def set_failure(self):
        """设置LLM服务不可用"""
        self._is_healthy = False
        print_status("LLM服务已模拟为不可用状态", "WARNING")

    def set_healthy(self):
        """恢复LLM服务"""
        self._is_healthy = True
        print_status("LLM服务已恢复正常", "SUCCESS")

    def is_healthy(self):
        return self._is_healthy


def scenario_llm_failure():
    """场景: LLM服务不可用"""
    print_section("场景1: LLM服务不可用")

    print_status("步骤1: 记录基线指标")
    baseline = run_evaluation_test(10)
    print(f"  基线指标: {json.dumps(baseline, indent=2)}")

    print_status("\n步骤2: 模拟LLM服务不可用")
    import src.domain.models.llm_factory as llm_factory

    original_create = llm_factory.create_llm_client

    def failing_create(*args, **kwargs):
        raise ConnectionError("模拟LLM服务不可用")

    llm_factory.create_llm_client = failing_create
    print_status("LLM客户端创建函数已替换为失败版本", "WARNING")

    print_status("\n步骤3: 运行评估测试")
    metrics = run_evaluation_test(10)
    print(f"  故障指标: {json.dumps(metrics, indent=2)}")

    print_status("\n步骤4: 恢复LLM服务")
    llm_factory.create_llm_client = original_create
    print_status("LLM客户端创建函数已恢复", "SUCCESS")

    print_status("\n步骤5: 验证服务恢复")
    recovery = run_evaluation_test(10)
    print(f"  恢复指标: {json.dumps(recovery, indent=2)}")

    print_section("场景1完成")


def scenario_db_connection_pool():
    """场景: 数据库连接池耗尽"""
    print_section("场景2: 数据库连接池耗尽")

    print_status("步骤1: 记录基线指标")
    baseline = run_evaluation_test(10)
    print(f"  基线指标: {json.dumps(baseline, indent=2)}")

    print_status("\n步骤2: 模拟连接池耗尽")
    import src.infra.db.session as db_session

    original_get_db = db_session.get_db

    connection_count = [0]
    max_connections = 5

    def limited_get_db():
        connection_count[0] += 1
        if connection_count[0] > max_connections:
            raise Exception("连接池已耗尽")
        return original_get_db()

    db_session.get_db = limited_get_db
    print_status(f"数据库连接限制为 {max_connections} 个", "WARNING")

    print_status("\n步骤3: 运行评估测试")
    metrics = run_evaluation_test(10)
    print(f"  故障指标: {json.dumps(metrics, indent=2)}")

    print_status("\n步骤4: 恢复连接池")
    db_session.get_db = original_get_db
    connection_count[0] = 0
    print_status("数据库连接已恢复", "SUCCESS")

    print_status("\n步骤5: 验证服务恢复")
    recovery = run_evaluation_test(10)
    print(f"  恢复指标: {json.dumps(recovery, indent=2)}")

    print_section("场景2完成")


def scenario_redis_failure():
    """场景: Redis缓存故障"""
    print_section("场景3: Redis缓存故障")

    print_status("步骤1: 记录基线指标")
    baseline = run_evaluation_test(10)
    print(f"  基线指标: {json.dumps(baseline, indent=2)}")

    print_status("\n步骤2: 模拟Redis故障")
    import src.distributed.redis_cache as redis_cache

    original_cache = redis_cache.redis_cache

    class FailingRedis:
        def __getattr__(self, name):
            raise ConnectionError("模拟Redis不可用")

    redis_cache.redis_cache = FailingRedis()
    print_status("Redis缓存已模拟为不可用", "WARNING")

    print_status("\n步骤3: 运行评估测试")
    metrics = run_evaluation_test(10)
    print(f"  故障指标: {json.dumps(metrics, indent=2)}")

    print_status("\n步骤4: 恢复Redis")
    redis_cache.redis_cache = original_cache
    print_status("Redis缓存已恢复", "SUCCESS")

    print_status("\n步骤5: 验证服务恢复")
    recovery = run_evaluation_test(10)
    print(f"  恢复指标: {json.dumps(recovery, indent=2)}")

    print_section("场景3完成")


def scenario_network_delay():
    """场景: 网络延迟增加"""
    print_section("场景4: 网络延迟增加")

    print_status("步骤1: 记录基线指标")
    baseline = run_evaluation_test(10)
    print(f"  基线指标: {json.dumps(baseline, indent=2)}")

    print_status("\n步骤2: 模拟网络延迟")
    import src.domain.models.llm_factory as llm_factory

    original_create = llm_factory.create_llm_client

    def delayed_create(*args, **kwargs):
        client = original_create(*args, **kwargs)
        original_chat = client.chat

        def delayed_chat(*args, **kwargs):
            time.sleep(2)
            return original_chat(*args, **kwargs)

        client.chat = delayed_chat
        return client

    llm_factory.create_llm_client = delayed_create
    print_status("LLM响应已添加2秒延迟", "WARNING")

    print_status("\n步骤3: 运行评估测试")
    metrics = run_evaluation_test(5)
    print(f"  故障指标: {json.dumps(metrics, indent=2)}")

    print_status("\n步骤4: 恢复网络")
    llm_factory.create_llm_client = original_create
    print_status("网络延迟已恢复", "SUCCESS")

    print_status("\n步骤5: 验证服务恢复")
    recovery = run_evaluation_test(10)
    print(f"  恢复指标: {json.dumps(recovery, indent=2)}")

    print_section("场景4完成")


def scenario_evaluator_registration():
    """场景: 评估器注册失败"""
    print_section("场景5: 评估器注册失败")

    print_status("步骤1: 记录基线指标")
    baseline = run_evaluation_test(10)
    print(f"  基线指标: {json.dumps(baseline, indent=2)}")

    print_status("\n步骤2: 模拟评估器注册失败")
    import src.domain.evaluators.evaluator_factory as ef

    original_get = ef.EvaluatorFactory.get

    def failing_get(evaluator_name, *args, **kwargs):
        if evaluator_name == "general":
            raise Exception("模拟评估器注册失败")
        return original_get(evaluator_name, *args, **kwargs)

    ef.EvaluatorFactory.get = failing_get
    print_status("general评估器已模拟为注册失败", "WARNING")

    print_status("\n步骤3: 运行评估测试")
    metrics = run_evaluation_test(10)
    print(f"  故障指标: {json.dumps(metrics, indent=2)}")

    print_status("\n步骤4: 恢复评估器注册")
    ef.EvaluatorFactory.get = original_get
    print_status("评估器注册已恢复", "SUCCESS")

    print_status("\n步骤5: 验证服务恢复")
    recovery = run_evaluation_test(10)
    print(f"  恢复指标: {json.dumps(recovery, indent=2)}")

    print_section("场景5完成")


def list_scenarios():
    """列出所有支持的场景"""
    scenarios = {
        "llm_failure": "LLM服务不可用",
        "db_connection_pool": "数据库连接池耗尽",
        "redis_failure": "Redis缓存故障",
        "network_delay": "网络延迟增加",
        "evaluator_registration": "评估器注册失败",
    }

    print("支持的故障演练场景:")
    for key, desc in scenarios.items():
        print(f"  - {key}: {desc}")


def main():
    parser = argparse.ArgumentParser(description="AI Eval Platform 故障演练脚本")
    parser.add_argument(
        "--scenario",
        type=str,
        help="要运行的场景名称",
        choices=[
            "llm_failure",
            "db_connection_pool",
            "redis_failure",
            "network_delay",
            "evaluator_registration",
        ],
    )
    parser.add_argument("--list", action="store_true", help="列出所有场景")

    args = parser.parse_args()

    if args.list:
        list_scenarios()
        return

    if not args.scenario:
        parser.print_help()
        return

    scenario_map = {
        "llm_failure": scenario_llm_failure,
        "db_connection_pool": scenario_db_connection_pool,
        "redis_failure": scenario_redis_failure,
        "network_delay": scenario_network_delay,
        "evaluator_registration": scenario_evaluator_registration,
    }

    print_status("警告: 本脚本仅用于测试环境，请勿在生产环境使用！", "WARNING")
    input("按 Enter 键继续...")

    scenario_func = scenario_map.get(args.scenario)
    if scenario_func:
        scenario_func()
    else:
        print_status(f"未知场景: {args.scenario}", "ERROR")


if __name__ == "__main__":
    main()
