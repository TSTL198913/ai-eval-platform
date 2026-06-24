"""
覆盖率趋势追踪脚本

功能：
1. 记录每次测试的覆盖率到历史文件
2. 生成覆盖率趋势报告
3. 标记覆盖率下降告警

使用方式：
    python -m src.infra.testing.coverage_tracker

    或在CI中集成：
    pytest --cov=src --cov-report=json
    python -m src.infra.testing.coverage_tracker --compare-baseline
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

try:
    import coverage  # noqa: F401

    HAS_COV = True
except ImportError:
    HAS_COV = False


# =====================================================================
# 配置
# =====================================================================

HISTORY_DIR = Path(".coverage_history")
HISTORY_FILE = HISTORY_DIR / "trends.json"
COVERAGE_JSON = Path("coverage.json")
BASELINE_FILE = HISTORY_DIR / "baseline.json"

DEFAULT_BRANCH_COVERAGE = 70
DEFAULT_LINE_COVERAGE = 80


# =====================================================================
# 覆盖率历史管理
# =====================================================================


class CoverageTracker:
    """覆盖率追踪器"""

    def __init__(self, history_dir: Path = HISTORY_DIR):
        self.history_dir = history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = history_dir / "trends.json"

    def load_history(self) -> list[dict]:
        """加载历史记录"""
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"历史记录加载失败: {e}")
            return []

    def save_history(self, history: list[dict]):
        """保存历史记录"""
        try:
            with open(self.history_file, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"历史记录保存失败: {e}")

    def get_current_coverage(self) -> dict | None:
        """获取当前覆盖率"""
        if not HAS_COV:
            print("coverage库未安装")
            return None

        if not COVERAGE_JSON.exists():
            print(f"覆盖率文件不存在: {COVERAGE_JSON}")
            return None

        try:
            with open(COVERAGE_JSON) as f:
                data = json.load(f)

            return {
                "timestamp": datetime.now().isoformat(),
                "total_lines": data["totals"]["n_lines"],
                "covered_lines": data["totals"]["covered_lines"],
                "line_coverage": data["totals"]["percent_covered"] / 100,
                "total_branches": data["totals"]["n_branches"],
                "covered_branches": data["totals"]["covered_branches"],
                "branch_coverage": data["totals"]["percent_covered_branches"] / 100,
            }

        except Exception as e:
            print(f"覆盖率数据解析失败: {e}")
            return None

    def record_coverage(self) -> dict:
        """记录当前覆盖率到历史"""
        current = self.get_current_coverage()
        if not current:
            return {}

        history = self.load_history()

        # 添加到历史
        history.append(current)

        # 只保留最近100条记录
        if len(history) > 100:
            history = history[-100:]

        self.save_history(history)
        print(f"覆盖率已记录到历史: {current['line_coverage']:.2%}")

        return current

    def compare_baseline(self, current: dict) -> dict:
        """与基准对比"""
        if not BASELINE_FILE.exists():
            print("基准文件不存在，跳过对比")
            return {"has_baseline": False}

        try:
            with open(BASELINE_FILE) as f:
                baseline = json.load(f)

            diff = {
                "has_baseline": True,
                "baseline_line": baseline.get("line_coverage", 0),
                "current_line": current.get("line_coverage", 0),
                "line_diff": current.get("line_coverage", 0) - baseline.get("line_coverage", 0),
                "baseline_branch": baseline.get("branch_coverage", 0),
                "current_branch": current.get("branch_coverage", 0),
                "branch_diff": current.get("branch_coverage", 0)
                - baseline.get("branch_coverage", 0),
            }

            return diff

        except Exception as e:
            print(f"基准对比失败: {e}")
            return {"has_baseline": False, "error": str(e)}

    def set_baseline(self):
        """设置当前覆盖率为基准"""
        current = self.get_current_coverage()
        if not current:
            print("无法获取当前覆盖率")
            return

        try:
            with open(BASELINE_FILE, "w") as f:
                json.dump(current, f, indent=2)
            print(
                f"基准已设置: line={current['line_coverage']:.2%}, branch={current['branch_coverage']:.2%}"
            )
        except Exception as e:
            print(f"基准保存失败: {e}")

    def generate_trend_report(self) -> str:
        """生成覆盖率趋势报告"""
        history = self.load_history()
        if not history:
            return "无历史数据"

        # 计算趋势
        recent = history[-10:] if len(history) >= 10 else history

        line_trend = []
        branch_trend = []
        for record in recent:
            line_trend.append(record.get("line_coverage", 0) * 100)
            branch_trend.append(record.get("branch_coverage", 0) * 100)

        avg_line = sum(line_trend) / len(line_trend)
        avg_branch = sum(branch_trend) / len(branch_trend)

        # 最新值
        latest = history[-1]
        latest_line = latest.get("line_coverage", 0) * 100
        latest_branch = latest.get("branch_coverage", 0) * 100

        # 趋势判断
        if len(recent) >= 2:
            first = recent[0]
            last = recent[-1]
            line_delta = (last.get("line_coverage", 0) - first.get("line_coverage", 0)) * 100
            branch_delta = (last.get("branch_coverage", 0) - first.get("branch_coverage", 0)) * 100
            line_trend = "↑" if line_delta > 0 else "↓" if line_delta < 0 else "→"
            branch_trend = "↑" if branch_delta > 0 else "↓" if branch_delta < 0 else "→"
        else:
            line_delta = branch_delta = 0
            line_trend = branch_trend = "—"

        report = f"""
================================================================================
                        覆盖率趋势报告
================================================================================

最新覆盖率: line={latest_line:.1f}% {line_trend} (delta={line_delta:+.1f}%)
            branch={latest_branch:.1f}% {branch_trend} (delta={branch_delta:+.1f}%)

最近{len(recent)}次平均: line={avg_line:.1f}%, branch={avg_branch:.1f}%

历史记录数: {len(history)}

--------------------------------------------------------------------------------
覆盖率走势 (最近{len(recent)}次)
--------------------------------------------------------------------------------
"""

        # 简单柱状图
        max_val = 100
        for _i, record in enumerate(recent):
            line = record.get("line_coverage", 0) * 100
            bar_len = int(line / max_val * 40)
            bar = "█" * bar_len + "░" * (40 - bar_len)
            timestamp = record.get("timestamp", "")[:19]
            report += f"{timestamp[-8:]} | {bar} {line:5.1f}%\n"

        report += (
            "--------------------------------------------------------------------------------\n"
        )

        return report

    def check_regression(self, current: dict, thresholds: dict = None) -> list[dict]:
        """检查覆盖率下降"""
        if thresholds is None:
            thresholds = {
                "line_coverage_min": DEFAULT_LINE_COVERAGE,
                "branch_coverage_min": DEFAULT_BRANCH_COVERAGE,
            }

        alerts = []

        # 检查最低阈值
        line_coverage = current.get("line_coverage", 0) * 100
        branch_coverage = current.get("branch_coverage", 0) * 100

        if line_coverage < thresholds.get("line_coverage_min", 0):
            alerts.append(
                {
                    "severity": (
                        "critical"
                        if line_coverage < thresholds["line_coverage_min"] - 10
                        else "warning"
                    ),
                    "type": "line_coverage",
                    "message": f"行覆盖率 {line_coverage:.1f}% 低于最低要求 {thresholds['line_coverage_min']}%",
                    "value": line_coverage,
                    "threshold": thresholds["line_coverage_min"],
                }
            )

        if branch_coverage < thresholds.get("branch_coverage_min", 0):
            alerts.append(
                {
                    "severity": (
                        "critical"
                        if branch_coverage < thresholds["branch_coverage_min"] - 10
                        else "warning"
                    ),
                    "type": "branch_coverage",
                    "message": f"分支覆盖率 {branch_coverage:.1f}% 低于最低要求 {thresholds['branch_coverage_min']}%",
                    "value": branch_coverage,
                    "threshold": thresholds["branch_coverage_min"],
                }
            )

        # 检查与历史对比
        diff = self.compare_baseline(current)
        if diff.get("has_baseline"):
            if diff["line_diff"] < -5:
                alerts.append(
                    {
                        "severity": "warning",
                        "type": "line_coverage_regression",
                        "message": f"行覆盖率下降 {abs(diff['line_diff']):.1f}%",
                        "value": diff["current_line"] * 100,
                        "baseline": diff["baseline_line"] * 100,
                        "diff": diff["line_diff"] * 100,
                    }
                )

        return alerts


# =====================================================================
# 主入口
# =====================================================================


def main():
    parser = argparse.ArgumentParser(description="覆盖率趋势追踪")
    parser.add_argument("--record", action="store_true", help="记录当前覆盖率")
    parser.add_argument("--baseline", action="store_true", help="设置基准覆盖率")
    parser.add_argument("--compare-baseline", action="store_true", help="与基准对比")
    parser.add_argument("--report", action="store_true", help="生成趋势报告")
    parser.add_argument("--check", action="store_true", help="检查覆盖率告警")
    parser.add_argument("--history", action="store_true", help="显示历史记录")

    args = parser.parse_args()

    tracker = CoverageTracker()

    if args.record:
        current = tracker.record_coverage()
        if current:
            print(f"行覆盖率: {current['line_coverage']:.2%}")
            print(f"分支覆盖率: {current['branch_coverage']:.2%}")

    elif args.baseline:
        tracker.set_baseline()

    elif args.compare_baseline:
        current = tracker.get_current_coverage()
        if current:
            diff = tracker.compare_baseline(current)
            if diff.get("has_baseline"):
                print(f"基准行覆盖率: {diff['baseline_line']:.2%}")
                print(f"当前行覆盖率: {diff['current_line']:.2%}")
                print(f"差异: {diff['line_diff']:+.2%}")

    elif args.report:
        print(tracker.generate_trend_report())

    elif args.check:
        current = tracker.get_current_coverage()
        if current:
            alerts = tracker.check_regression(current)
            if alerts:
                print("覆盖率告警:")
                for alert in alerts:
                    print(f"  [{alert['severity'].upper()}] {alert['message']}")
            else:
                print("无覆盖率告警")

    elif args.history:
        history = tracker.load_history()
        if history:
            print(f"共 {len(history)} 条历史记录")
            for record in history[-10:]:
                print(
                    f"  {record.get('timestamp', '')[:19]}: line={record.get('line_coverage', 0) * 100:.1f}%"
                )
        else:
            print("无历史记录")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
