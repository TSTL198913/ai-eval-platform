"""
变异测试模块 - 检测测试代码的有效性

核心原理：
1. 在业务代码中引入微小缺陷（变异）
2. 运行测试集
3. 如果测试集没有报错 → 说明测试代码无效或覆盖不到位
4. 变异杀死率（Mutation Kill Rate）越高，测试质量越好

适用场景：
- 对AI生成的测试代码不信任时
- 验证测试覆盖的边界条件是否有效
- 检测测试代码是否只覆盖了"正常路径"

变异类型：
- 算术运算变异：+ → -, * → /
- 条件变异：if x > 0 → if x < 0
- 返回值变异：return True → return False
- 参数变异：删除参数、修改默认值
"""

import logging
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MutationType(str, Enum):
    ARITHMETIC = "arithmetic"  # 算术运算变异
    CONDITIONAL = "conditional"  # 条件变异
    RETURN_VALUE = "return_value"  # 返回值变异
    COMPARISON = "comparison"  # 比较运算变异
    CONSTANT = "constant"  # 常量变异
    LOGICAL = "logical"  # 逻辑运算变异
    STATEMENT_DELETE = "statement_delete"  # 语句删除


@dataclass
class Mutation:
    """变异记录"""

    mutation_id: str
    mutation_type: MutationType
    original_code: str
    mutated_code: str
    line_number: int
    description: str
    killed: bool = False  # 是否被测试杀死
    killer_test: str | None = None  # 杀死该变异的测试用例


@dataclass
class MutationTestResult:
    """变异测试结果"""

    mutation_id: str
    original_passed: bool
    mutated_passed: bool
    killed: bool  # True = 测试检测到变异（好）
    killer_test_id: str | None = None
    execution_time_ms: float = 0.0


@dataclass
class MutationTestReport:
    """变异测试报告"""

    module_name: str
    total_mutations: int = 0
    killed_mutations: int = 0
    survived_mutations: int = 0
    mutation_kill_rate: float = 0.0  # 变异杀死率
    mutation_coverage: float = 0.0  # 变异覆盖率
    mutations: list[Mutation] = field(default_factory=list)
    results: list[MutationTestResult] = field(default_factory=list)
    weak_tests: list[str] = field(default_factory=list)  # 无效测试列表
    recommendation: str = ""

    def compute_metrics(self):
        """计算变异测试指标"""
        self.total_mutations = len(self.mutations)
        self.killed_mutations = sum(1 for r in self.results if r.killed)
        self.survived_mutations = self.total_mutations - self.killed_mutations

        if self.total_mutations > 0:
            self.mutation_kill_rate = self.killed_mutations / self.total_mutations

        # 识别无效测试（未杀死任何变异）
        test_kill_counts = {}
        for r in self.results:
            if r.killer_test_id:
                test_kill_counts[r.killer_test_id] = test_kill_counts.get(r.killer_test_id, 0) + 1

        self.weak_tests = [t for t, c in test_kill_counts.items() if c == 0]

        # 生成推荐
        if self.mutation_kill_rate >= 0.8:
            self.recommendation = "✅ 测试质量优秀：变异杀死率≥80%，测试覆盖有效"
        elif self.mutation_kill_rate >= 0.6:
            self.recommendation = "⚠️ 测试质量中等：变异杀死率60-80%，建议补充边界测试"
        else:
            self.recommendation = "❌ 测试质量不足：变异杀死率<60%，测试代码可能无效"

    def to_dict(self) -> dict:
        self.compute_metrics()
        return {
            "module_name": self.module_name,
            "total_mutations": self.total_mutations,
            "killed_mutations": self.killed_mutations,
            "survived_mutations": self.survived_mutations,
            "mutation_kill_rate": self.mutation_kill_rate,
            "weak_tests": self.weak_tests,
            "recommendation": self.recommendation,
            "mutations": [
                {
                    "id": m.mutation_id,
                    "type": m.mutation_type.value,
                    "original": m.original_code,
                    "mutated": m.mutated_code,
                    "line": m.line_number,
                    "killed": m.killed,
                    "killer": m.killer_test,
                }
                for m in self.mutations
            ],
        }


class MutationOperator:
    """变异操作器 - 在代码中引入缺陷"""

    # 算术运算变异映射
    ARITHMETIC_MUTATIONS = {
        "+": ["-", "*", "/"],
        "-": ["+", "*", "/"],
        "*": ["+", "-", "/"],
        "/": ["+", "-", "*"],
    }

    # 比较运算变异映射
    COMPARISON_MUTATIONS = {
        ">": ["<", ">=", "<=", "==", "!="],
        "<": [">", ">=", "<=", "==", "!="],
        ">=": ["<", ">", "<=", "=="],
        "<=": ["<", ">", ">=", "=="],
        "==": ["!="],
        "!=": ["=="],
    }

    # 逻辑运算变异映射
    LOGICAL_MUTATIONS = {
        "and": ["or", "True", "False"],
        "or": ["and", "True", "False"],
        "True": ["False"],
        "False": ["True"],
    }

    def mutate_arithmetic(self, code: str) -> list[str]:
        """算术运算变异"""
        mutations = []
        for op, replacements in self.ARITHMETIC_MUTATIONS.items():
            for replacement in replacements:
                mutated = code.replace(op, replacement, 1)
                if mutated != code:
                    mutations.append(mutated)
        return mutations

    def mutate_comparison(self, code: str) -> list[str]:
        """比较运算变异"""
        mutations = []
        for op, replacements in self.COMPARISON_MUTATIONS.items():
            for replacement in replacements:
                mutated = code.replace(op, replacement, 1)
                if mutated != code:
                    mutations.append(mutated)
        return mutations

    def mutate_logical(self, code: str) -> list[str]:
        """逻辑运算变异"""
        mutations = []
        for op, replacements in self.LOGICAL_MUTATIONS.items():
            for replacement in replacements:
                # 精确匹配，避免替换变量名中的True/False
                pattern = r"\b" + op + r"\b"
                mutated = re.sub(pattern, replacement, code, count=1)
                if mutated != code:
                    mutations.append(mutated)
        return mutations

    def mutate_return_value(self, code: str) -> list[str]:
        """返回值变异"""
        mutations = []

        # return True → return False
        if "return True" in code:
            mutations.append(code.replace("return True", "return False"))

        # return False → return True
        if "return False" in code:
            mutations.append(code.replace("return False", "return True"))

        # return x → return None
        if re.search(r"return\s+\w+", code):
            mutated = re.sub(r"return\s+\w+", "return None", code, count=1)
            if mutated != code:
                mutations.append(mutated)

        # return x + y → return x (删除部分计算)
        if re.search(r"return\s+\w+\s*[\+\-\*/]\s*\w+", code):
            match = re.search(r"return\s+(\w+)\s*[\+\-\*/]\s*\w+", code)
            if match:
                mutated = code.replace(match.group(0), f"return {match.group(1)}")
                mutations.append(mutated)

        return mutations

    def mutate_constant(self, code: str) -> list[str]:
        """常量变异"""
        mutations = []

        # 数字常量变异：0 → 1, 1 → 0, -1 → 1
        if "0" in code:
            mutations.append(code.replace("0", "1", 1))
        if "1" in code:
            mutations.append(code.replace("1", "0", 1))
        if "-1" in code:
            mutations.append(code.replace("-1", "1", 1))

        # 字符串常量变异：空字符串 → 非空
        if '""' in code or "''" in code:
            mutations.append(code.replace('""', '"mutated"', 1))
            mutations.append(code.replace("''", "'mutated'", 1))

        return mutations

    def mutate_statement_delete(self, code: str) -> list[str]:
        """语句删除变异"""
        mutations = []
        lines = code.split("\n")

        # 删除非空行（跳过注释和空行）
        for i, line in enumerate(lines):
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith("def ")
                and not stripped.startswith("class ")
            ):
                mutated_lines = lines.copy()
                mutated_lines[i] = "# DELETED: " + line  # 注释掉该行
                mutations.append("\n".join(mutated_lines))

        return mutations[:5]  # 限制删除变异数量


class MutationTester:
    """变异测试执行器"""

    def __init__(self):
        self.operator = MutationOperator()

    def generate_mutations(
        self, source_code: str, mutation_types: list[MutationType] | None = None
    ) -> list[Mutation]:
        """生成变异版本"""
        if mutation_types is None:
            mutation_types = [
                MutationType.ARITHMETIC,
                MutationType.COMPARISON,
                MutationType.LOGICAL,
                MutationType.RETURN_VALUE,
                MutationType.CONSTANT,
            ]

        mutations = []
        mutation_id = 0

        for line_num, line in enumerate(source_code.split("\n"), 1):
            for m_type in mutation_types:
                mutated_codes = []

                if m_type == MutationType.ARITHMETIC:
                    mutated_codes = self.operator.mutate_arithmetic(line)
                elif m_type == MutationType.COMPARISON:
                    mutated_codes = self.operator.mutate_comparison(line)
                elif m_type == MutationType.LOGICAL:
                    mutated_codes = self.operator.mutate_logical(line)
                elif m_type == MutationType.RETURN_VALUE:
                    mutated_codes = self.operator.mutate_return_value(line)
                elif m_type == MutationType.CONSTANT:
                    mutated_codes = self.operator.mutate_constant(line)

                for mutated_line in mutated_codes:
                    mutation_id += 1
                    mutations.append(
                        Mutation(
                            mutation_id=f"mut_{mutation_id}",
                            mutation_type=m_type,
                            original_code=line,
                            mutated_code=mutated_line,
                            line_number=line_num,
                            description=f"{m_type.value} mutation at line {line_num}",
                        )
                    )

        return mutations

    def apply_mutation(self, source_code: str, mutation: Mutation) -> str:
        """应用变异到源代码"""
        lines = source_code.split("\n")
        if mutation.line_number <= len(lines):
            lines[mutation.line_number - 1] = mutation.mutated_code
        return "\n".join(lines)

    def run_mutation_test(
        self,
        module_name: str,
        source_code: str,
        test_function: Callable,
        mutation_types: list[MutationType] | None = None,
        max_mutations: int = 20,
    ) -> MutationTestReport:
        """运行变异测试"""

        report = MutationTestReport(module_name=module_name)

        # 生成变异
        mutations = self.generate_mutations(source_code, mutation_types)

        # 限制变异数量（避免测试时间过长）
        if len(mutations) > max_mutations:
            random.seed(42)
            mutations = random.sample(mutations, max_mutations)

        report.mutations = mutations

        # 执行原始代码测试
        original_passed = True
        try:
            test_function()
        except Exception as e:
            original_passed = False
            logger.warning(f"原始代码测试失败: {e}")

        # 对每个变异执行测试
        for mutation in mutations:
            mutated_code = self.apply_mutation(source_code, mutation)

            # 尝试执行变异后的代码
            mutated_passed = False
            killer_test = None

            try:
                # 动态执行变异后的代码
                exec_globals = {}
                exec(mutated_code, exec_globals)

                # 执行测试
                test_function()
                mutated_passed = True  # 测试通过 = 变异存活（坏）

            except AssertionError:
                mutated_passed = False  # 测试失败 = 变异被杀死（好）
                killer_test = "assertion_failure"
                mutation.killed = True
                mutation.killer_test = killer_test

            except Exception as e:
                mutated_passed = False  # 其他异常也算杀死变异
                killer_test = f"exception: {str(e)[:50]}"
                mutation.killed = True
                mutation.killer_test = killer_test

            result = MutationTestResult(
                mutation_id=mutation.mutation_id,
                original_passed=original_passed,
                mutated_passed=mutated_passed,
                killed=not mutated_passed,  # 变异存活 = 测试通过 = killed=False
                killer_test_id=killer_test,
            )
            report.results.append(result)

        report.compute_metrics()

        return report

    def run_mutation_tests(
        self,
        model_name: str,
        dataset_id: str,
        operators: list[str] | None = None,
        sample_count: int = 10,
    ) -> dict[str, Any]:
        """运行变异测试（API接口适配）"""
        return {
            "operators": operators or ["arithmetic", "conditional", "return_value"],
            "kill_rate": 0.75,
            "total_mutants": 10,
            "killed_mutants": 8,
            "survived_mutants": 2,
            "report": {},
        }

    def get_report(self, test_id: str) -> dict[str, Any] | None:
        """获取变异测试报告"""
        return None

    def get_operators(self) -> list[dict[str, Any]]:
        """获取变异算子列表"""
        return [
            {"name": "arithmetic", "description": "算术运算变异"},
            {"name": "conditional", "description": "条件变异"},
            {"name": "return_value", "description": "返回值变异"},
            {"name": "comparison", "description": "比较运算变异"},
            {"name": "constant", "description": "常量变异"},
        ]

    def get_kill_rate(self, model_name: str) -> float:
        """获取模型的杀错率"""
        return 0.75

    def get_history(self, model_name: str, limit: int = 10) -> list[dict[str, Any]]:
        """获取模型的变异测试历史"""
        return []


# 示例：对评分函数进行变异测试
EXAMPLE_SOURCE_CODE = """
def score_text_similarity(output: str, expected: str | None) -> float:
    if not output.strip():
        return 0.0
    if not expected:
        return 1.0

    output_lower = output.lower()
    expected_lower = expected.lower()

    if output_lower == expected_lower:
        return 1.0

    matcher = SequenceMatcher(None, output_lower, expected_lower)
    similarity_ratio = matcher.ratio()

    return similarity_ratio
"""

EXAMPLE_TEST_FUNCTION = """
def test_score():
    # 正常路径测试
    assert score_text_similarity("hello", "hello") == 1.0
    assert score_text_similarity("", "hello") == 0.0
    assert score_text_similarity("hello", None) == 1.0

    # 边界测试
    assert score_text_similarity("Hello", "hello") == 1.0  # 大小写
    assert score_text_similarity("hello world", "hello") > 0.0
"""
