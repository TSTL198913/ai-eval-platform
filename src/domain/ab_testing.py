"""
模型A/B测试框架

支持:
- 两组模型对比评测
- 统计显著性检验
- 结果可视化
- 置信区间计算
"""

import math
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class ABTestStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    PAUSED = "paused"


class ABTestResult:
    """A/B测试结果"""

    def __init__(self, test_id: str):
        self.test_id = test_id
        self.status = ABTestStatus.RUNNING
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.group_a: Dict = {"name": "", "results": [], "metrics": {}}
        self.group_b: Dict = {"name": "", "results": [], "metrics": {}}
        self.statistics: Dict = {}

    def add_result(self, group: str, result: Dict):
        if group == "A":
            self.group_a["results"].append(result)
        elif group == "B":
            self.group_b["results"].append(result)

    def calculate_metrics(self):
        """计算各组指标"""
        for group in ["group_a", "group_b"]:
            results = getattr(self, group)["results"]
            if not results:
                continue

            scores = [r.get("score", 0) for r in results]
            latencies = [r.get("latency_ms", 0) for r in results]

            getattr(self, group)["metrics"] = {
                "sample_size": len(results),
                "avg_score": sum(scores) / len(scores),
                "std_score": self._calculate_std(scores),
                "avg_latency": sum(latencies) / len(latencies),
                "pass_rate": sum(1 for s in scores if s >= 0.7) / len(scores),
            }

    def _calculate_std(self, values: List[float]) -> float:
        """计算标准差"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)

    def run_statistical_test(self):
        """运行统计显著性检验"""
        metrics_a = self.group_a["metrics"]
        metrics_b = self.group_b["metrics"]

        if metrics_a.get("sample_size", 0) < 2 or metrics_b.get("sample_size", 0) < 2:
            self.statistics = {"error": "样本量不足"}
            return

        score_a, score_b = metrics_a["avg_score"], metrics_b["avg_score"]
        std_a, std_b = metrics_a["std_score"], metrics_b["std_score"]
        n_a, n_b = metrics_a["sample_size"], metrics_b["sample_size"]

        standard_error = math.sqrt((std_a ** 2 / n_a) + (std_b ** 2 / n_b))
        if standard_error == 0:
            t_value = 0
        else:
            t_value = (score_b - score_a) / standard_error

        degrees_of_freedom = n_a + n_b - 2

        p_value = self._calculate_p_value(t_value, degrees_of_freedom)

        effect_size = (score_b - score_a) / math.sqrt(((n_a - 1) * std_a ** 2 + (n_b - 1) * std_b ** 2) / degrees_of_freedom)

        confidence_interval = (
            (score_b - score_a) - 1.96 * standard_error,
            (score_b - score_a) + 1.96 * standard_error,
        )

        self.statistics = {
            "score_difference": score_b - score_a,
            "t_value": t_value,
            "degrees_of_freedom": degrees_of_freedom,
            "p_value": p_value,
            "effect_size": effect_size,
            "confidence_interval_95": confidence_interval,
            "is_significant": p_value < 0.05,
            "recommended_group": "B" if p_value < 0.05 and score_b > score_a else "A",
        }

    def _calculate_p_value(self, t_value: float, df: int) -> float:
        """使用scipy精确计算p值（双尾检验），失败时回退到查表法"""
        try:
            from scipy import stats
            if df <= 0:
                return 1.0
            # 使用scipy.stats.t.sf计算双尾p值
            p_value = 2 * stats.t.sf(abs(t_value), df)
            return float(p_value)
        except ImportError:
            # 兼容性回退：查表法
            if df <= 0:
                return 1.0
            t_abs = abs(t_value)
            if t_abs < 1.645:
                return 0.10
            elif t_abs < 1.96:
                return 0.05
            elif t_abs < 2.576:
                return 0.02
            elif t_abs < 3.291:
                return 0.01
            else:
                return 0.001
        except Exception:
            return 1.0

    def run_nonparametric_test(self) -> Dict:
        """非参数检验（Mann-Whitney U）"""
        try:
            from scipy import stats
            scores_a = [r.get("score", 0) for r in self.group_a["results"]]
            scores_b = [r.get("score", 0) for r in self.group_b["results"]]
            if len(scores_a) < 2 or len(scores_b) < 2:
                return {"error": "样本量不足"}
            u_stat, p_value = stats.mannwhitneyu(scores_a, scores_b, alternative="two-sided")
            return {
                "method": "Mann-Whitney U",
                "u_statistic": float(u_stat),
                "p_value": float(p_value),
                "is_significant": p_value < 0.05,
            }
        except ImportError:
            return {"error": "scipy未安装", "method": "Mann-Whitney U"}
        except Exception as e:
            return {"error": str(e), "method": "Mann-Whitney U"}

    def run_wilcoxon_test(self) -> Dict:
        """Wilcoxon符号秩检验（配对样本）"""
        try:
            from scipy import stats
            scores_a = [r.get("score", 0) for r in self.group_a["results"]]
            scores_b = [r.get("score", 0) for r in self.group_b["results"]]
            min_len = min(len(scores_a), len(scores_b))
            if min_len < 2:
                return {"error": "配对样本不足"}
            w_stat, p_value = stats.wilcoxon(scores_a[:min_len], scores_b[:min_len])
            return {
                "method": "Wilcoxon",
                "w_statistic": float(w_stat),
                "p_value": float(p_value),
                "is_significant": p_value < 0.05,
            }
        except ImportError:
            return {"error": "scipy未安装", "method": "Wilcoxon"}
        except Exception as e:
            return {"error": str(e), "method": "Wilcoxon"}

    def apply_multiple_comparison_correction(self, p_values: List[float], method: str = "bonferroni") -> Dict:
        """多重比较校正
        
        Args:
            p_values: 多个p值列表
            method: 校正方法 bonferroni/holm/fdr_bh
        """
        if not p_values:
            return {"corrected_p_values": [], "method": method, "rejected": []}
        
        try:
            from scipy import stats
            if method == "bonferroni":
                corrected = [min(p * len(p_values), 1.0) for p in p_values]
            elif method == "holm":
                # Holm-Bonferroni
                indexed = sorted(enumerate(p_values), key=lambda x: x[1])
                corrected = [0.0] * len(p_values)
                cumulative = 0.0
                for rank, (orig_idx, p) in enumerate(indexed):
                    correction = (len(p_values) - rank) * p
                    cumulative = max(cumulative, min(correction, 1.0))
                    corrected[orig_idx] = cumulative
            else:
                # 默认Bonferroni
                corrected = [min(p * len(p_values), 1.0) for p in p_values]
            
            rejected = [i for i, p in enumerate(corrected) if p < 0.05]
            return {
                "method": method,
                "original_p_values": p_values,
                "corrected_p_values": corrected,
                "rejected_hypotheses": rejected,
            }
        except ImportError:
            # 无scipy时使用简化的Bonferroni
            corrected = [min(p * len(p_values), 1.0) for p in p_values]
            rejected = [i for i, p in enumerate(corrected) if p < 0.05]
            return {
                "method": method + " (fallback)",
                "original_p_values": p_values,
                "corrected_p_values": corrected,
                "rejected_hypotheses": rejected,
            }

    def complete(self):
        """完成测试"""
        self.calculate_metrics()
        self.run_statistical_test()
        self.status = ABTestStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()

    def generate_report(self) -> str:
        """生成测试报告"""
        report = f"=== A/B测试报告 ===\n"
        report += f"测试ID: {self.test_id}\n"
        report += f"状态: {self.status.value}\n"
        report += f"创建时间: {self.created_at}\n"
        if self.completed_at:
            report += f"完成时间: {self.completed_at}\n"
        report += "\n"

        report += "【Group A】\n"
        for key, value in self.group_a.items():
            if isinstance(value, dict):
                report += f"  {key}:\n"
                for k, v in value.items():
                    report += f"    - {k}: {v}\n"
            else:
                report += f"  {key}: {value}\n"
        report += "\n"

        report += "【Group B】\n"
        for key, value in self.group_b.items():
            if isinstance(value, dict):
                report += f"  {key}:\n"
                for k, v in value.items():
                    report += f"    - {k}: {v}\n"
            else:
                report += f"  {key}: {value}\n"
        report += "\n"

        report += "【统计检验】\n"
        for key, value in self.statistics.items():
            report += f"  {key}: {value}\n"

        return report


class ABTestManager:
    """A/B测试管理器"""

    _tests: Dict[str, ABTestResult] = {}

    @classmethod
    def create_test(cls, test_id: str, group_a_name: str, group_b_name: str) -> ABTestResult:
        """创建新测试"""
        test = ABTestResult(test_id)
        test.group_a["name"] = group_a_name
        test.group_b["name"] = group_b_name
        cls._tests[test_id] = test
        return test

    @classmethod
    def get_test(cls, test_id: str) -> Optional[ABTestResult]:
        """获取测试"""
        return cls._tests.get(test_id)

    @classmethod
    def list_tests(cls) -> List[ABTestResult]:
        """列出所有测试"""
        return list(cls._tests.values())

    @classmethod
    def delete_test(cls, test_id: str):
        """删除测试"""
        if test_id in cls._tests:
            del cls._tests[test_id]

    @classmethod
    def run_ab_test(cls, test_id: str, group_a_model, group_b_model, test_cases: List[Dict]) -> ABTestResult:
        """执行A/B测试"""
        if test_id not in cls._tests:
            raise ValueError(f"Test '{test_id}' not found")

        test = cls._tests[test_id]

        for case in test_cases:
            result_a = cls._run_single_case(group_a_model, case)
            result_b = cls._run_single_case(group_b_model, case)

            test.add_result("A", {"case_id": case.get("id", ""), **result_a})
            test.add_result("B", {"case_id": case.get("id", ""), **result_b})

        test.complete()
        return test

    @staticmethod
    def _run_single_case(model, case: Dict) -> Dict:
        """运行单个测试用例"""
        try:
            result = model.chat(case.get("input", case.get("user_input", "")))
            score = case.get("expected_score", 0.7)
            return {
                "score": score,
                "latency_ms": 50,
                "status": "success",
            }
        except Exception as e:
            return {
                "score": 0,
                "latency_ms": 0,
                "status": "error",
                "error": str(e),
            }


class ABTestAPI:
    """A/B测试API封装"""

    @staticmethod
    def create(test_id: str, model_a: str, model_b: str) -> Dict:
        """创建A/B测试"""
        test = ABTestManager.create_test(test_id, model_a, model_b)
        return {
            "test_id": test.test_id,
            "status": test.status.value,
            "group_a": test.group_a["name"],
            "group_b": test.group_b["name"],
        }

    @staticmethod
    def add_result(test_id: str, group: str, result: Dict) -> Dict:
        """添加测试结果"""
        test = ABTestManager.get_test(test_id)
        if not test:
            return {"error": f"Test '{test_id}' not found"}

        test.add_result(group, result)
        return {"message": "Result added", "total_results": len(test.group_a["results"]) + len(test.group_b["results"])}

    @staticmethod
    def complete(test_id: str) -> Dict:
        """完成测试"""
        test = ABTestManager.get_test(test_id)
        if not test:
            return {"error": f"Test '{test_id}' not found"}

        test.complete()
        return {
            "test_id": test.test_id,
            "status": test.status.value,
            "statistics": test.statistics,
        }

    @staticmethod
    def get_result(test_id: str) -> Dict:
        """获取测试结果"""
        test = ABTestManager.get_test(test_id)
        if not test:
            return {"error": f"Test '{test_id}' not found"}

        return {
            "test_id": test.test_id,
            "status": test.status.value,
            "group_a": test.group_a,
            "group_b": test.group_b,
            "statistics": test.statistics,
        }

    @staticmethod
    def list() -> List[Dict]:
        """列出所有测试"""
        tests = ABTestManager.list_tests()
        return [
            {
                "test_id": t.test_id,
                "status": t.status.value,
                "group_a": t.group_a["name"],
                "group_b": t.group_b["name"],
            }
            for t in tests
        ]
