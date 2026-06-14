"""
AI Evaluation Platform SDK 使用示例

展示 SDK 的主要功能和用法。
"""

import asyncio
import os

# 设置 API 密钥
API_KEY = os.getenv("AI_EVAL_API_KEY", "your-api-key-here")


async def example_basic_evaluation():
    """基础评测示例"""
    from ai_eval_sdk import Client

    print("\n=== 基础评测示例 ===")

    async with Client(api_key=API_KEY) as client:
        # 评测 GPT-4 在 MMLU 数据集上的表现
        result = await client.evaluate(
            model="gpt-4",
            dataset="mmlu",
            metrics=["accuracy", "latency", "cost"]
        )

        print(f"评测结果: {result}")
        print(f"准确率: {result.metrics.get('accuracy', 0):.2f}")
        print(f"延迟: {result.latency_ms:.1f}ms")


async def example_custom_prompts():
    """自定义提示词评测"""
    from ai_eval_sdk import Client

    print("\n=== 自定义提示词评测 ===")

    async with Client(api_key=API_KEY) as client:
        # 使用自定义提示词评测
        custom_prompts = [
            "What is the capital of France?",
            "Explain quantum computing in simple terms.",
            "Write a Python function to reverse a string.",
        ]

        result = await client.evaluate(
            model="gpt-4",
            custom_prompts=custom_prompts,
            metrics=["accuracy", "relevance"]
        )

        print(f"自定义评测结果: {result}")
        for i, detail in enumerate(result.details.get("responses", [])):
            print(f"\n问题 {i+1}: {custom_prompts[i]}")
            print(f"回答: {detail.get('response', '')[:100]}...")


async def example_model_comparison():
    """模型对比示例"""
    from ai_eval_sdk import Client

    print("\n=== 模型对比示例 ===")

    async with Client(api_key=API_KEY) as client:
        # 对比多个模型
        report = await client.compare(
            models=[
                {"model": "gpt-4", "dataset": "mmlu"},
                {"model": "gpt-3.5-turbo", "dataset": "mmlu"},
                {"model": "claude-3-opus", "dataset": "mmlu"},
            ],
            metrics=["accuracy", "latency", "cost"]
        )

        # 打印对比摘要
        report.print_summary()

        # 获取排名
        print("\n排名详情:")
        for model, rank in report.rankings.items():
            print(f"  {model}: 第 {rank} 名")


async def example_async_evaluation():
    """异步评测示例"""
    from ai_eval_sdk import Client

    print("\n=== 异步评测示例 ===")

    async with Client(api_key=API_KEY) as client:
        # 提交异步评测任务
        task_id = await client.evaluate_async(
            model="gpt-4",
            dataset="humaneval",
            metrics=["pass_rate", "code_quality"]
        )

        print(f"任务已提交，ID: {task_id}")

        # 等待结果
        for i in range(10):
            result = await client.get_result(task_id)
            if result:
                print(f"\n评测完成: {result}")
                break
            print(f"等待中... ({i+1}/10)")
            await asyncio.sleep(2)


async def example_list_resources():
    """列出可用资源"""
    from ai_eval_sdk import Client

    print("\n=== 可用资源列表 ===")

    async with Client(api_key=API_KEY) as client:
        # 获取可用数据集
        datasets = await client.list_datasets()
        print("\n可用数据集:")
        for ds in datasets[:5]:  # 只显示前 5 个
            print(f"  - {ds['name']}: {ds['description']}")

        # 获取可用模型
        models = await client.list_models()
        print("\n可用模型:")
        for model in models[:5]:  # 只显示前 5 个
            print(f"  - {model['name']} ({model['provider']})")


async def example_usage_stats():
    """使用统计"""
    from ai_eval_sdk import Client

    print("\n=== API 使用统计 ===")

    async with Client(api_key=API_KEY) as client:
        usage = await client.get_usage()
        print(f"\n本月调用次数: {usage.get('total_calls', 0)}")
        print(f"剩余配额: {usage.get('remaining_quota', 0)}")
        print(f"本月费用: ¥{usage.get('monthly_cost', 0):.2f}")


def example_sync_client():
    """同步客户端示例"""
    from ai_eval_sdk import SyncClient, compare, evaluate

    print("\n=== 同步客户端示例 ===")

    # 使用同步客户端
    client = SyncClient(api_key=API_KEY)

    result = client.evaluate(model="gpt-4", dataset="mmlu")
    print(f"同步评测结果: {result}")

    client.close()

    # 或使用快捷函数
    print("\n=== 快捷函数示例 ===")

    result = evaluate("gpt-4", "mmlu", api_key=API_KEY)
    print(f"快捷评测结果: {result}")

    report = compare(
        [
            {"model": "gpt-4", "dataset": "mmlu"},
            {"model": "claude-3", "dataset": "mmlu"},
        ],
        api_key=API_KEY,
    )
    report.print_summary()


async def example_batch_evaluation():
    """批量评测示例"""
    from ai_eval_sdk import Client

    print("\n=== 批量评测示例 ===")

    async with Client(api_key=API_KEY) as client:
        models = ["gpt-4", "gpt-3.5-turbo", "claude-3"]
        datasets = ["mmlu", "humaneval", "gsm8k"]

        # 并发评测多个模型
        tasks = []
        for model in models:
            for dataset in datasets:
                task = client.evaluate_async(model=model, dataset=dataset)
                tasks.append(task)

        task_ids = await asyncio.gather(*tasks)
        print(f"已提交 {len(task_ids)} 个评测任务")

        # 等待所有任务完成
        results = []
        for task_id in task_ids:
            for _ in range(20):  # 最多等待 40 秒
                result = await client.get_result(task_id)
                if result:
                    results.append(result)
                    break
                await asyncio.sleep(2)

        # 汇总结果
        print("\n批量评测结果汇总:")
        for result in results:
            print(f"  {result.model} @ {result.dataset}: {result.metrics}")


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("AI Evaluation Platform SDK 使用示例")
    print("=" * 60)

    await example_basic_evaluation()
    await example_custom_prompts()
    await example_model_comparison()
    await example_async_evaluation()
    await example_list_resources()
    await example_usage_stats()
    example_sync_client()
    await example_batch_evaluation()

    print("\n" + "=" * 60)
    print("所有示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
