"""
AI评估平台 - 端到端演示脚本

运行方式：python demo.py

演示内容：
1. 代码评估
2. 语义相似度评估
3. 事实性评估
4. 安全性评估
5. 评估结果缓存
6. 并发评估能力
"""

import asyncio
import json
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock

from src.engine import EvaluationEngine
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus
from src.infra.cache import EvaluationCache


def print_header(title):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(result):
    """打印评估结果"""
    if result.response:
        print(f"  状态: {result.response.evaluation_status.value}")
        print(f"  分数: {result.response.score if result.response.score is not None else 'N/A'}")
        print(f"  置信度: {result.response.confidence if result.response.confidence is not None else 'N/A'}")
        print(f"  延迟: {result.latency_ms:.2f}ms")
        if result.response.data:
            print(f"  详细数据: {json.dumps(result.response.data, ensure_ascii=False)[:100]}...")
        if result.response.error:
            print(f"  错误: {result.response.error}")
    else:
        print(f"  状态: {result.status.value}")
        print(f"  延迟: {result.latency_ms:.2f}ms")
        if result.error_message:
            print(f"  错误: {result.error_message}")


def demo_code_evaluation(engine):
    """演示代码评估"""
    print_header("1. 代码评估 (Code Evaluation)")
    
    code_request = EvaluationSchema(
        id="demo-code-001",
        type="code",
        payload={
            "code": """
def calculate_factorial(n):
    if n < 0:
        raise ValueError("负数没有阶乘")
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
""",
            "metadata": {"language": "python"},
        },
    )
    
    result = engine.run(code_request)
    print_result(result)


def demo_semantic_evaluation(engine):
    """演示语义相似度评估"""
    print_header("2. 语义相似度评估 (Semantic Evaluation)")
    
    semantic_request = EvaluationSchema(
        id="demo-semantic-001",
        type="semantic",
        payload={
            "user_input": "解释什么是人工智能",
            "actual_output": "人工智能是计算机科学的一个分支，使机器能够模拟人类智能。",
            "expected_output": "人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新的技术科学。",
        },
    )
    
    result = engine.run(semantic_request)
    print_result(result)


def demo_factuality_evaluation(engine):
    """演示事实性评估"""
    print_header("3. 事实性评估 (Factuality Evaluation)")
    
    factuality_request = EvaluationSchema(
        id="demo-factuality-001",
        type="factuality",
        payload={
            "claim": "光速是每秒30万公里",
            "expected_output": "光速在真空中约为每秒299792公里",
            "evidence": "根据爱因斯坦的相对论，光速在真空中是恒定的，约为299,792,458米/秒。",
        },
    )
    
    result = engine.run(factuality_request)
    print_result(result)


def demo_security_evaluation(engine, mock_client):
    """演示安全性评估"""
    print_header("4. 安全性评估 (Security Evaluation)")
    
    mock_client.chat.return_value = json.dumps({
        "score": 0.25,
        "confidence": 0.9,
        "vulnerabilities": [
            {"type": "SQL注入", "severity": "high", "line": 3},
            {"type": "XSS", "severity": "medium", "line": 8}
        ],
        "recommendations": ["使用参数化查询", "对用户输入进行转义"]
    })
    
    security_request = EvaluationSchema(
        id="demo-security-001",
        type="security",
        payload={
            "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
            "metadata": {"language": "python"},
        },
    )
    
    result = engine.run(security_request)
    print_result(result)


def demo_cache_functionality():
    """演示缓存功能"""
    print_header("5. 缓存功能演示 (Cache Functionality)")
    
    cache = EvaluationCache(ttl_seconds=300, max_size=100)
    
    cache.set("eval:test-001", {"score": 0.85, "status": "success"})
    print("  ✅ 设置缓存")
    
    cached_result = cache.get("eval:test-001")
    print(f"  ✅ 获取缓存: {cached_result}")
    
    stats = cache.get_stats()
    print(f"  ✅ 缓存统计: 命中={stats['hits']}, 未命中={stats['misses']}, 淘汰={stats['evictions']}")
    
    cache.invalidate("eval:test-001")
    cached_result = cache.get("eval:test-001")
    print(f"  ✅ 删除缓存后获取: {cached_result}")


def demo_concurrent_evaluation(engine):
    """演示并发评估能力"""
    print_header("6. 并发评估演示 (Concurrent Evaluation)")
    
    results = []
    errors = []
    
    def evaluate_task(task_id):
        try:
            request = EvaluationSchema(
                id=f"concurrent-{task_id}",
                type="factuality",
                payload={
                    "claim": f"测试任务{task_id}: 水在标准大气压下沸点是100度",
                    "expected_output": "水的沸点是100摄氏度",
                    "evidence": "标准大气压下，水的沸点是100摄氏度。",
                },
            )
            result = engine.run(request)
            results.append((task_id, result))
        except Exception as e:
            errors.append((task_id, e))
    
    threads = []
    start_time = time.time()
    
    for i in range(5):
        t = threading.Thread(target=evaluate_task, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    elapsed_time = time.time() - start_time
    
    print(f"  并发任务数: 5")
    print(f"  总耗时: {elapsed_time:.2f}秒")
    print(f"  成功: {len(results)}, 失败: {len(errors)}")
    
    for task_id, result in results[:3]:
        if result.response:
            print(f"    任务{task_id}: 状态={result.response.evaluation_status.value}, 分数={result.response.score}")


def main():
    """主函数"""
    print(f"\n{'='*60}")
    print(f"  AI评估平台 - 端到端演示")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    mock_client = MagicMock()
    mock_client.chat.return_value = json.dumps({
        "score": 0.85,
        "confidence": 0.92,
        "dimensions": {"accuracy": 0.9, "completeness": 0.8}
    })
    
    engine = EvaluationEngine(client=mock_client)
    
    demo_code_evaluation(engine)
    demo_semantic_evaluation(engine)
    demo_factuality_evaluation(engine)
    demo_security_evaluation(engine, mock_client)
    demo_cache_functionality()
    demo_concurrent_evaluation(engine)
    
    print(f"\n{'='*60}")
    print(f"  演示完成！")
    print(f"{'='*60}")
    print("\n项目核心特性：")
    print("  • 支持多种评估类型：代码、语义、事实性、安全性")
    print("  • 内置缓存机制，提升评估性能")
    print("  • 支持并发评估，提高吞吐量")
    print("  • 完整的错误处理和状态管理")
    print("  • 分布式锁和限流保护")
    print("  • 可扩展的评估器架构")


if __name__ == "__main__":
    main()