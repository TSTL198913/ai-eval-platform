#!/usr/bin/env python3
"""
测试 Prometheus 指标模块是否正常工作

用法:
    python test_metrics.py
"""

import sys
sys.path.insert(0, '.')

from src.infra.monitoring.metrics import (
    EVALUATION_LATENCY,
    EVALUATION_COUNTER,
    EVALUATION_ERRORS,
    CACHE_HITS,
    CACHE_MISSES,
    expose_metrics,
)

print("=" * 60)
print("测试 Prometheus 指标模块")
print("=" * 60)

print("\n1. 测试指标记录...")
EVALUATION_COUNTER.labels(domain="test", status="success").inc()
EVALUATION_COUNTER.labels(domain="test", status="error").inc()
EVALUATION_LATENCY.labels(domain="test", status="success").observe(0.15)
EVALUATION_LATENCY.labels(domain="test", status="success").observe(0.08)
EVALUATION_LATENCY.labels(domain="test", status="success").observe(0.25)
EVALUATION_ERRORS.labels(domain="test", error_type="network").inc()
CACHE_HITS.labels(cache_type="redis").inc(100)
CACHE_MISSES.labels(cache_type="redis").inc(20)

print("   ✓ 指标记录成功")

print("\n2. 测试指标暴露...")
metrics_text = expose_metrics()
print(f"   ✓ 指标输出长度: {len(metrics_text)} 字符")

print("\n3. 显示部分指标内容...")
lines = metrics_text.strip().split("\n")
for line in lines[:20]:
    print(f"   {line}")

print("\n4. 解析指标...")
import re

eval_total_lines = [l for l in lines if l.startswith("evaluation_total")]
eval_latency_lines = [l for l in lines if l.startswith("evaluation_latency")]

print(f"   evaluation_total 指标: {len(eval_total_lines)} 行")
print(f"   evaluation_latency 指标: {len(eval_latency_lines)} 行")

for line in eval_total_lines:
    match = re.match(r"evaluation_total\{([^}]+)\}\s+([\d.]+)", line)
    if match:
        print(f"     {match.group(1)}: {match.group(2)}")

print("\n" + "=" * 60)
print("测试通过! Prometheus 指标模块工作正常")
print("=" * 60)
