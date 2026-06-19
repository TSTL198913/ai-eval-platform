"""
红蓝对抗测试模块 - 确保AI生成的测试代码与业务代码独立验证

核心原则：
- 业务代码由AI生成 → 测试代码必须由人类编写（或反之）
- 防止AI让测试代码迎合业务代码的逻辑漏洞

使用方式：
1. Blue Team: AI生成的业务代码 + AI生成的测试代码
2. Red Team: 人类编写的破坏性测试集（核心断言）
3. 对抗结果: Red Team测试必须通过，才能证明Blue Team代码正确
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TeamRole(str, Enum):
    BLUE = "blue"   # AI生成代码 + AI生成测试
    RED = "red"     # 人类编写的破坏性测试


class TestType(str, Enum):
    FUNCTIONAL = "functional"       # 功能正确性
    EDGE_CASE = "edge_case"         # 边界条件
    SECURITY = "security"           # 安全漏洞
    PERFORMANCE = "performance"     # 性能压力
    CONCURRENCY = "concurrency"     # 并发安全


@dataclass
class TestCase:
    """红蓝对抗测试用例"""
    id: str
    team: TeamRole
    test_type: TestType
    description: str
    input_data: Dict[str, Any]
    expected_behavior: str  # 期望行为描述（自然语言）
    assertions: List[str]   # 断言列表
    priority: int = 1       # 1-5, 5最高
    author: str = "unknown" # 编写者（human/ai）
    created_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "team": self.team.value,
            "test_type": self.test_type.value,
            "description": self.description,
            "input_data": self.input_data,
            "expected_behavior": self.expected_behavior,
            "assertions": self.assertions,
            "priority": self.priority,
            "author": self.author,
            "created_at": self.created_at,
        }


@dataclass
class RedBlueTestResult:
    """红蓝对抗测试结果"""
    test_id: str
    team: TeamRole
    passed: bool
    actual_output: Any
    failure_reason: Optional[str] = None
    execution_time_ms: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "test_id": self.test_id,
            "team": self.team.value,
            "passed": self.passed,
            "actual_output": str(self.actual_output),
            "failure_reason": self.failure_reason,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class RedBlueTestReport:
    """红蓝对抗测试报告"""
    module_name: str
    blue_team_results: List[RedBlueTestResult] = field(default_factory=list)
    red_team_results: List[RedBlueTestResult] = field(default_factory=list)
    blue_pass_rate: float = 0.0
    red_pass_rate: float = 0.0
    overall_trust_score: float = 0.0  # 综合信任分数
    recommendation: str = ""
    
    def compute_scores(self):
        """计算通过率和信任分数"""
        blue_passed = sum(1 for r in self.blue_team_results if r.passed)
        blue_total = len(self.blue_team_results)
        self.blue_pass_rate = blue_passed / blue_total if blue_total > 0 else 0
        
        red_passed = sum(1 for r in self.red_team_results if r.passed)
        red_total = len(self.red_team_results)
        self.red_pass_rate = red_passed / red_total if red_total > 0 else 0
        
        # 信任分数 = Red Team通过率 × 权重（Red Team更重要）
        # Blue Team通过率作为参考
        self.overall_trust_score = (
            self.red_pass_rate * 0.7 +  # Red Team权重70%
            self.blue_pass_rate * 0.3   # Blue Team权重30%
        )
        
        # 生成推荐
        if self.red_pass_rate >= 0.9:
            self.recommendation = "✅ 高度可信：Red Team测试通过率≥90%，可以信任"
        elif self.red_pass_rate >= 0.7:
            self.recommendation = "⚠️ 中度可信：Red Team测试通过率70-90%，建议人工复核"
        else:
            self.recommendation = "❌ 不可信：Red Team测试通过率<70%，必须修复"
    
    def to_dict(self) -> Dict:
        self.compute_scores()
        return {
            "module_name": self.module_name,
            "blue_team_results": [r.to_dict() for r in self.blue_team_results],
            "red_team_results": [r.to_dict() for r in self.red_team_results],
            "blue_pass_rate": self.blue_pass_rate,
            "red_pass_rate": self.red_pass_rate,
            "overall_trust_score": self.overall_trust_score,
            "recommendation": self.recommendation,
        }


class RedBlueTestManager:
    """红蓝对抗测试管理器"""
    
    def __init__(self, test_data_dir: Optional[str] = None):
        self.test_data_dir = Path(test_data_dir) if test_data_dir else Path(__file__).parent / "data"
        self.blue_tests: List[TestCase] = []
        self.red_tests: List[TestCase] = []
    
    def load_test_suite(self, module_name: str) -> Dict[str, List[TestCase]]:
        """加载指定模块的红蓝测试集"""
        blue_file = self.test_data_dir / f"{module_name}_blue.json"
        red_file = self.test_data_dir / f"{module_name}_red.json"
        
        blue_tests = []
        if blue_file.exists():
            with open(blue_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("tests", []):
                    blue_tests.append(TestCase(
                        id=item["id"],
                        team=TeamRole.BLUE,
                        test_type=TestType(item["test_type"]),
                        description=item["description"],
                        input_data=item["input_data"],
                        expected_behavior=item["expected_behavior"],
                        assertions=item["assertions"],
                        priority=item.get("priority", 1),
                        author=item.get("author", "ai"),
                        created_at=item.get("created_at", ""),
                    ))
        
        red_tests = []
        if red_file.exists():
            with open(red_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("tests", []):
                    red_tests.append(TestCase(
                        id=item["id"],
                        team=TeamRole.RED,
                        test_type=TestType(item["test_type"]),
                        description=item["description"],
                        input_data=item["input_data"],
                        expected_behavior=item["expected_behavior"],
                        assertions=item["assertions"],
                        priority=item.get("priority", 5),  # Red Team默认高优先级
                        author=item.get("author", "human"),
                        created_at=item.get("created_at", ""),
                    ))
        
        self.blue_tests = blue_tests
        self.red_tests = red_tests
        
        return {"blue": blue_tests, "red": red_tests}
    
    def execute_test(self, test_case: TestCase, target_function: callable) -> RedBlueTestResult:
        """执行单个测试用例"""
        import time
        
        start_time = time.time()
        actual_output = None
        passed = False
        failure_reason = None
        
        try:
            # 执行目标函数
            actual_output = target_function(**test_case.input_data)
            
            # 验证断言
            for assertion in test_case.assertions:
                if not self._evaluate_assertion(assertion, actual_output):
                    passed = False
                    failure_reason = f"断言失败: {assertion}"
                    break
            else:
                passed = True
                
        except Exception as e:
            passed = False
            failure_reason = f"执行异常: {str(e)}"
            actual_output = str(e)
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        return RedBlueTestResult(
            test_id=test_case.id,
            team=test_case.team,
            passed=passed,
            actual_output=actual_output,
            failure_reason=failure_reason,
            execution_time_ms=execution_time_ms,
        )
    
    def _evaluate_assertion(self, assertion: str, actual_output: Any) -> bool:
        """评估断言"""
        # 简化实现：支持基本断言类型
        if assertion.startswith("equals:"):
            expected = assertion.split(":", 1)[1].strip()
            return str(actual_output) == expected
        elif assertion.startswith("contains:"):
            expected = assertion.split(":", 1)[1].strip()
            return expected in str(actual_output)
        elif assertion.startswith("not_null"):
            return actual_output is not None
        elif assertion.startswith("type:"):
            expected_type = assertion.split(":", 1)[1].strip()
            return type(actual_output).__name__ == expected_type
        elif assertion.startswith("greater_than:"):
            threshold = float(assertion.split(":", 1)[1].strip())
            return float(actual_output) > threshold
        elif assertion.startswith("less_than:"):
            threshold = float(assertion.split(":", 1)[1].strip())
            return float(actual_output) < threshold
        else:
            # 默认：检查输出是否包含断言文本
            return assertion in str(actual_output)
    
    def run_red_blue_test(self, module_name: str, target_function: callable) -> RedBlueTestReport:
        """运行红蓝对抗测试"""
        test_suite = self.load_test_suite(module_name)
        
        report = RedBlueTestReport(module_name=module_name)
        
        # 执行Blue Team测试
        for test_case in test_suite["blue"]:
            result = self.execute_test(test_case, target_function)
            report.blue_team_results.append(result)
        
        # 执行Red Team测试（破坏性测试）
        for test_case in test_suite["red"]:
            result = self.execute_test(test_case, target_function)
            report.red_team_results.append(result)
        
        report.compute_scores()
        
        return report


# 示例：为"评估器工厂"模块创建红蓝测试集
EXAMPLE_RED_TEST_SUITE = {
    "tests": [
        {
            "id": "red_evaluator_factory_001",
            "test_type": "edge_case",
            "description": "测试未注册评估器的处理",
            "input_data": {"evaluator_name": "nonexistent_evaluator_xyz"},
            "expected_behavior": "应抛出DomainLogicError，而不是返回None或空对象",
            "assertions": ["contains:DOMAIN_ERROR", "contains:未找到"],
            "priority": 5,
            "author": "human",
        },
        {
            "id": "red_evaluator_factory_002",
            "test_type": "security",
            "description": "测试SQL注入式评估器名称",
            "input_data": {"evaluator_name": "general; DROP TABLE users;"},
            "expected_behavior": "应拒绝执行，返回安全错误",
            "assertions": ["contains:invalid", "contains:name"],
            "priority": 5,
            "author": "human",
        },
        {
            "id": "red_evaluator_factory_003",
            "test_type": "edge_case",
            "description": "测试空字符串评估器名称",
            "input_data": {"evaluator_name": ""},
            "expected_behavior": "应返回错误，而不是默认选择",
            "assertions": ["contains:empty", "contains:required"],
            "priority": 5,
            "author": "human",
        },
        {
            "id": "red_evaluator_factory_004",
            "test_type": "concurrency",
            "description": "测试并发注册同一评估器",
            "input_data": {"concurrent_count": 100, "evaluator_name": "concurrent_test"},
            "expected_behavior": "应正确处理并发注册，不丢失数据",
            "assertions": ["equals:100"],  # 期望100次注册都成功
            "priority": 4,
            "author": "human",
        },
        {
            "id": "red_evaluator_factory_005",
            "test_type": "performance",
            "description": "测试大量评估器注册的性能",
            "input_data": {"count": 1000},
            "expected_behavior": "注册1000个评估器应在1秒内完成",
            "assertions": ["less_than:1000"],  # 执行时间<1000ms
            "priority": 3,
            "author": "human",
        },
    ]
}

EXAMPLE_BLUE_TEST_SUITE = {
    "tests": [
        {
            "id": "blue_evaluator_factory_001",
            "test_type": "functional",
            "description": "测试正常评估器获取",
            "input_data": {"evaluator_name": "general"},
            "expected_behavior": "应返回GeneralEvaluator实例",
            "assertions": ["not_null", "type:GeneralEvaluator"],
            "priority": 1,
            "author": "ai",
        },
        {
            "id": "blue_evaluator_factory_002",
            "test_type": "functional",
            "description": "测试评估器evaluate方法",
            "input_data": {"evaluator_name": "general", "request": {"id": "test", "type": "general", "payload": {"user_input": "hello"}}},
            "expected_behavior": "应返回DomainResponse",
            "assertions": ["contains:score", "contains:is_valid"],
            "priority": 1,
            "author": "ai",
        },
    ]
}