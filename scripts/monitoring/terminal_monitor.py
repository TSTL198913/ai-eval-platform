#!/usr/bin/env python3
"""
AI Eval Platform 终端监控脚本

无需Docker，直接连接FastAPI的/metrics端点，实时展示关键指标。

用法:
    python terminal_monitor.py
    python terminal_monitor.py --host localhost --port 8000 --interval 2

功能:
    - 实时显示评估请求速率、成功率、错误率
    - 显示P99/P95/P50延迟
    - 显示缓存命中率
    - 显示数据库连接状态
    - 显示评估器调用分布
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error

from collections import defaultdict
from typing import Dict, List, Optional, Tuple


class MetricParser:
    """Prometheus格式指标解析器"""

    def __init__(self, metrics_text: str):
        self.metrics_text = metrics_text
        self.metrics = self._parse()

    def _parse(self) -> Dict[str, Dict[Tuple[str, ...], float]]:
        result = defaultdict(dict)
        lines = self.metrics_text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = re.match(r"^(\w+)(\{[^\}]+\})?\s+([\d.eE+-]+)", line)
            if match:
                name = match.group(1)
                labels_str = match.group(2) or ""
                value = float(match.group(3))

                labels = []
                if labels_str:
                    label_pairs = labels_str[1:-1].split(",")
                    for pair in label_pairs:
                        key, val = pair.split("=")
                        labels.append((key.strip(), val.strip().strip('"')))
                labels = tuple(sorted(labels))

                result[name][labels] = value

        return result

    def get_counter(self, name: str, labels: Dict[str, str] = None) -> float:
        """获取计数器指标（支持部分标签匹配）"""
        target_labels_dict = labels or {}
        counter_values = self.metrics.get(name, {})
        
        for labels_tuple, value in counter_values.items():
            labels_dict = dict(labels_tuple)
            match = True
            for key, val in target_labels_dict.items():
                if labels_dict.get(key) != val:
                    match = False
                    break
            if match:
                return value
        
        return 0.0

    def get_histogram_quantile(self, name: str, quantile: float, labels: Dict[str, str] = None) -> float:
        """获取直方图分位数"""
        target_labels = self._dict_to_tuple(labels or {})
        quantile_key = target_labels + (("quantile", str(quantile)),)
        return self.metrics.get(f"{name}_bucket", {}).get(quantile_key, 0.0)

    def get_histogram_summary(self, name: str, labels: Dict[str, str] = None) -> Dict[str, float]:
        """获取直方图汇总统计（支持部分标签匹配）"""
        target_labels_dict = labels or {}

        total_sum = 0.0
        total_count = 0.0

        sum_values = self.metrics.get(f"{name}_sum", {})
        for labels_tuple, value in sum_values.items():
            labels_dict = dict(labels_tuple)
            match = True
            for key, val in target_labels_dict.items():
                if labels_dict.get(key) != val:
                    match = False
                    break
            if match:
                total_sum += value

        count_values = self.metrics.get(f"{name}_count", {})
        for labels_tuple, value in count_values.items():
            labels_dict = dict(labels_tuple)
            match = True
            for key, val in target_labels_dict.items():
                if labels_dict.get(key) != val:
                    match = False
                    break
            if match:
                total_count += value

        if total_count == 0:
            return {"p50": 0, "p95": 0, "p99": 0, "avg": 0, "count": 0}

        buckets = {}
        bucket_key_prefix = name + "_bucket"
        for labels_tuple, value in self.metrics.get(bucket_key_prefix, {}).items():
            labels_dict = dict(labels_tuple)
            match = True
            for key, val in target_labels_dict.items():
                if labels_dict.get(key) != val:
                    match = False
                    break
            if match:
                le_value = labels_dict.get("le")
                if le_value:
                    try:
                        if le_value == "+Inf":
                            buckets[float("inf")] = value
                        else:
                            buckets[float(le_value)] = value
                    except ValueError:
                        pass

        p50 = self._calc_quantile(buckets, 0.5, total_count)
        p95 = self._calc_quantile(buckets, 0.95, total_count)
        p99 = self._calc_quantile(buckets, 0.99, total_count)

        return {
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "avg": total_sum / total_count,
            "count": int(total_count),
        }

    def _calc_quantile(self, buckets: Dict[float, float], q: float, total_count: float) -> float:
        """计算分位数"""
        if not buckets:
            return 0.0

        sorted_buckets = sorted(buckets.items())
        target = q * total_count

        for upper_bound, count in sorted_buckets:
            if count >= target:
                return upper_bound

        return sorted_buckets[-1][0] if sorted_buckets else 0.0

    def _dict_to_tuple(self, labels: Dict[str, str]) -> Tuple[Tuple[str, str], ...]:
        return tuple(sorted(labels.items()))


class TerminalMonitor:
    """终端监控器"""

    def __init__(self, host: str = "localhost", port: int = 8000, interval: int = 2):
        self.host = host
        self.port = port
        self.interval = interval
        self.metrics_url = f"http://{host}:{port}/metrics"
        self.prev_metrics = {}
        self.start_time = time.time()

    def fetch_metrics(self) -> Optional[str]:
        """从/metrics端点获取指标"""
        try:
            req = urllib.request.Request(self.metrics_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.read().decode("utf-8")
        except urllib.error.URLError as e:
            print(f"[ERROR] 无法连接到 {self.metrics_url}: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] 获取指标失败: {e}")
            return None

    def calculate_rates(self, parser: MetricParser) -> Dict[str, float]:
        """计算速率指标"""
        rates = {}
        current_time = time.time()
        elapsed = current_time - self.start_time

        total_success = parser.get_counter("evaluation_total", {"status": "success"})
        total_error = parser.get_counter("evaluation_total", {"status": "error"})
        total_requests = total_success + total_error

        prev_success = self.prev_metrics.get("success", 0)
        prev_error = self.prev_metrics.get("error", 0)
        prev_total = prev_success + prev_error

        if elapsed > 0:
            rates["requests_per_second"] = total_requests / elapsed if elapsed > 0 else 0
        else:
            rates["requests_per_second"] = 0

        if total_requests > 0:
            rates["success_rate"] = (total_success / total_requests) * 100
            rates["error_rate"] = (total_error / total_requests) * 100
        else:
            rates["success_rate"] = 0
            rates["error_rate"] = 0

        self.prev_metrics = {
            "success": total_success,
            "error": total_error,
            "total": total_requests,
            "time": current_time,
        }

        return rates

    def get_evaluator_distribution(self, parser: MetricParser) -> List[Tuple[str, int]]:
        """获取评估器调用分布"""
        distribution = []
        evaluation_counter = parser.metrics.get("evaluation_total", {})

        for labels, count in evaluation_counter.items():
            label_dict = dict(labels)
            domain = label_dict.get("domain", "unknown")
            if domain != "other":
                distribution.append((domain, int(count)))

        distribution.sort(key=lambda x: x[1], reverse=True)
        return distribution

    def get_cache_metrics(self, parser: MetricParser) -> Dict[str, float]:
        """获取缓存指标"""
        hits = parser.get_counter("cache_hits_total")
        misses = parser.get_counter("cache_misses_total")

        total = hits + misses
        hit_rate = (hits / total) * 100 if total > 0 else 0

        return {
            "hits": int(hits),
            "misses": int(misses),
            "hit_rate": hit_rate,
        }

    def display(self):
        """显示监控面板"""
        while True:
            metrics_text = self.fetch_metrics()
            if not metrics_text:
                time.sleep(self.interval)
                continue

            parser = MetricParser(metrics_text)
            rates = self.calculate_rates(parser)
            latency = parser.get_histogram_summary("evaluation_latency_seconds")
            cache = self.get_cache_metrics(parser)
            evaluator_dist = self.get_evaluator_distribution(parser)

            self.clear_screen()
            self.print_header()
            self.print_request_metrics(rates)
            self.print_latency_metrics(latency)
            self.print_cache_metrics(cache)
            self.print_evaluator_distribution(evaluator_dist)
            self.print_footer()

            time.sleep(self.interval)

    def clear_screen(self):
        """清屏"""
        print("\033[H\033[J", end="")

    def print_header(self):
        """打印头部信息"""
        uptime = int(time.time() - self.start_time)
        uptime_str = self.format_uptime(uptime)
        print(f"{'='*70}")
        print(f"  AI Eval Platform - 终端监控")
        print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')} | 运行时长: {uptime_str}")
        print(f"  数据源: {self.metrics_url}")
        print(f"{'='*70}")

    def print_request_metrics(self, rates: Dict[str, float]):
        """打印请求指标"""
        print(f"\n  [请求指标]")
        print(f"  {'-'*40}")
        print(f"  请求速率:       {rates['requests_per_second']:>8.2f} req/s")
        print(f"  成功率:         {rates['success_rate']:>8.2f} %")
        print(f"  错误率:         {rates['error_rate']:>8.2f} %")

        if rates["error_rate"] > 5:
            print(f"  ⚠️  警告: 错误率超过5%!")

    def print_latency_metrics(self, latency: Dict[str, float]):
        """打印延迟指标"""
        print(f"\n  [延迟指标]")
        print(f"  {'-'*40}")
        print(f"  请求总数:       {latency['count']:>8d}")
        print(f"  P50延迟:        {latency['p50']*1000:>8.1f} ms")
        print(f"  P95延迟:        {latency['p95']*1000:>8.1f} ms")
        print(f"  P99延迟:        {latency['p99']*1000:>8.1f} ms")
        print(f"  平均延迟:       {latency['avg']*1000:>8.1f} ms")

        if latency["p99"] > 5:
            print(f"  ⚠️  警告: P99延迟超过5秒!")

    def print_cache_metrics(self, cache: Dict[str, float]):
        """打印缓存指标"""
        print(f"\n  [缓存指标]")
        print(f"  {'-'*40}")
        print(f"  缓存命中:       {cache['hits']:>8d}")
        print(f"  缓存未命中:     {cache['misses']:>8d}")
        print(f"  命中率:         {cache['hit_rate']:>8.2f} %")

        if cache["hit_rate"] < 80 and (cache["hits"] + cache["misses"]) > 100:
            print(f"  ⚠️  警告: 缓存命中率低于80%!")

    def print_evaluator_distribution(self, distribution: List[Tuple[str, int]]):
        """打印评估器分布"""
        print(f"\n  [评估器调用分布]")
        print(f"  {'-'*40}")

        if not distribution:
            print(f"  暂无数据")
            return

        max_name_len = max(len(name) for name, _ in distribution)
        total = sum(count for _, count in distribution)

        for name, count in distribution[:10]:
            percentage = (count / total) * 100 if total > 0 else 0
            bar_length = int(percentage / 5)
            bar = "█" * bar_length + "░" * (20 - bar_length)
            print(f"  {name:{max_name_len}}: {count:>6d} ({percentage:>5.1f}%) [{bar}]")

        if len(distribution) > 10:
            remaining = sum(count for _, count in distribution[10:])
            print(f"  ... 还有 {len(distribution) - 10} 个评估器 ({remaining} 次调用)")

    def print_footer(self):
        """打印底部信息"""
        print(f"\n  {'='*70}")
        print(f"  按 Ctrl+C 退出")
        print(f"{'='*70}")

    def format_uptime(self, seconds: int) -> str:
        """格式化运行时长"""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if days > 0:
            return f"{days}天 {hours}小时 {minutes}分钟"
        elif hours > 0:
            return f"{hours}小时 {minutes}分钟 {secs}秒"
        elif minutes > 0:
            return f"{minutes}分钟 {secs}秒"
        else:
            return f"{secs}秒"


def main():
    parser = argparse.ArgumentParser(description="AI Eval Platform 终端监控")
    parser.add_argument("--host", type=str, default="localhost", help="服务主机")
    parser.add_argument("--port", type=int, default=8000, help="服务端口")
    parser.add_argument("--interval", type=int, default=2, help="刷新间隔(秒)")

    args = parser.parse_args()

    print(f"正在连接到 http://{args.host}:{args.port}/metrics ...")

    monitor = TerminalMonitor(host=args.host, port=args.port, interval=args.interval)

    try:
        monitor.display()
    except KeyboardInterrupt:
        print("\n监控已退出")
        sys.exit(0)


if __name__ == "__main__":
    main()
