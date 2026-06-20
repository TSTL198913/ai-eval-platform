#!/usr/bin/env python
"""
性能基线比较脚本

比较当前性能测试结果与基线，输出对比报告。
用于检测性能回归。
"""

import json
import os
from datetime import datetime
from pathlib import Path


def load_json_file(filepath):
    """加载 JSON 文件"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def compare_metric(name, current, baseline, threshold=10.0):
    """比较单个指标"""
    if baseline == 0:
        if current == 0:
            return {"status": "stable", "change": 0}
        return {"status": "changed", "change": 100}

    change = ((current - baseline) / baseline) * 100

    if abs(change) <= threshold:
        return {"status": "stable", "change": round(change, 2)}
    elif change > 0:
        return {"status": "regressed", "change": round(change, 2)}
    else:
        return {"status": "improved", "change": round(change, 2)}


def main():
    """主函数"""
    print("=" * 60)
    print("性能基线比较报告")
    print("=" * 60)
    print(f"执行时间: {datetime.now().isoformat()}")
    print()

    # 加载基线和当前结果
    baseline_dir = Path("tests/benchmark_results")
    baseline_file = baseline_dir / "baseline.json"

    if not baseline_file.exists():
        print("⚠️  未找到基线文件，首次运行将创建基线")
        print()
        print("建议: 运行完整的性能测试后，再次执行此脚本进行基线比较")
        return

    baseline_data = load_json_file(baseline_file)

    # 查找最新的测试结果
    result_files = list(baseline_dir.glob("benchmark_*.json"))
    result_files = [f for f in result_files if f.name != "baseline.json"]

    if not result_files:
        print("⚠️  未找到性能测试结果文件")
        return

    # 使用最新的结果
    latest_result = sorted(result_files)[-1]
    current_data = load_json_file(latest_result)

    print(f"基线文件: {baseline_file}")
    print(f"当前结果: {latest_result}")
    print()

    # 比较每个指标
    metrics_to_compare = [
        ("avg_duration_ms", "平均延迟", "ms"),
        ("p50_ms", "P50延迟", "ms"),
        ("p95_ms", "P95延迟", "ms"),
        ("p99_ms", "P99延迟", "ms"),
        ("throughput", "吞吐量", "req/s"),
        ("error_rate", "错误率", "%"),
    ]

    print("-" * 60)
    print("指标对比")
    print("-" * 60)

    total_metrics = 0
    stable_metrics = 0
    regressed_metrics = 0
    improved_metrics = 0

    for result in current_data.get("results", []):
        result_name = result.get("name", "unknown")
        baseline_result = None

        for b in baseline_data.get("results", []):
            if b.get("name") == result_name:
                baseline_result = b
                break

        if not baseline_result:
            print(f"\n📊 {result_name}")
            print("  状态: 新增指标（无基线）")
            continue

        print(f"\n📊 {result_name}")

        for metric_key, metric_name, unit in metrics_to_compare:
            if metric_key not in result or metric_key not in baseline_result:
                continue

            current_val = result[metric_key]
            baseline_val = baseline_result[metric_key]

            comparison = compare_metric(metric_name, current_val, baseline_val)

            status_icon = {
                "stable": "✅",
                "regressed": "❌",
                "improved": "🚀",
            }.get(comparison["status"], "❓")

            print(f"  {metric_name}:")
            print(f"    基线: {baseline_val:.2f} {unit}")
            print(f"    当前: {current_val:.2f} {unit}")
            print(f"    变化: {comparison['change']:+.2f}% {status_icon}")

            total_metrics += 1
            if comparison["status"] == "stable":
                stable_metrics += 1
            elif comparison["status"] == "regressed":
                regressed_metrics += 1
            else:
                improved_metrics += 1

    print()
    print("-" * 60)
    print("汇总")
    print("-" * 60)
    print(f"总指标数: {total_metrics}")
    print(
        f"稳定: {stable_metrics} ({stable_metrics/total_metrics*100:.1f}%)"
        if total_metrics
        else "稳定: 0"
    )
    print(
        f"回归: {regressed_metrics} ({regressed_metrics/total_metrics*100:.1f}%)"
        if total_metrics
        else "回归: 0"
    )
    print(
        f"改善: {improved_metrics} ({improved_metrics/total_metrics*100:.1f}%)"
        if total_metrics
        else "改善: 0"
    )
    print()

    if regressed_metrics > 0:
        print("⚠️  警告: 检测到性能回归，请检查上述回归的指标")
        print("建议: 调查回归原因，如有必要更新基线")
        return 1
    elif improved_metrics > total_metrics * 0.3:
        print("🎉 好消息: 检测到显著的性能改善！")
        print("建议: 考虑更新基线以反映新的性能水平")
    else:
        print("✅ 性能状态正常，未检测到显著回归")

    print()
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
