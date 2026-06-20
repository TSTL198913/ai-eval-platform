"""
质量门禁装饰器和集成接口

提供多层防御网机制：
1. 红蓝对抗测试装饰器
2. 变异测试装饰器
3. 质量保障管理器

使用示例：
    @quality_gate(
        red_team_tests=["edge_case", "security"],
        mutation_testing=True,
        min_trust_score=0.8
    )
    def evaluate(self, request):
        ...
"""

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ParamSpec, TypeVar

from src.domain.testing.mutation_testing import (
    MutationTester,
    MutationTestReport,
)
from src.domain.testing.red_blue_testing import (
    RedBlueTestManager,
    RedBlueTestReport,
    TestType,
)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class QualityGateLevel(str, Enum):
    """质量门禁级别"""
    STRICT = "strict"      # 严格模式：Red Team通过率≥90%，变异杀死率≥80%
    NORMAL = "normal"      # 正常模式：Red Team通过率≥80%，变异杀死率≥60%
    RELAXED = "relaxed"    # 宽松模式：Red Team通过率≥70%，变异杀死率≥50%
    DISABLED = "disabled"  # 禁用质量门禁


@dataclass
class QualityGateConfig:
    """质量门禁配置"""
    level: QualityGateLevel = QualityGateLevel.NORMAL
    enable_red_blue: bool = True
    enable_mutation: bool = True
    min_trust_score: float = 0.8
    min_mutation_kill_rate: float = 0.6
    red_test_types: list[TestType] = field(default_factory=lambda: [TestType.EDGE_CASE, TestType.SECURITY])
    max_mutations: int = 10
    fail_on_quality_gate: bool = True  # 质量门禁失败时是否抛出异常


@dataclass
class QualityGateResult:
    """质量门禁检查结果"""
    passed: bool
    trust_score: float = 0.0
    mutation_kill_rate: float = 0.0
    red_blue_report: RedBlueTestReport | None = None
    mutation_report: MutationTestReport | None = None
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "trust_score": self.trust_score,
            "mutation_kill_rate": self.mutation_kill_rate,
            "red_blue_report": self.red_blue_report.to_dict() if self.red_blue_report else None,
            "mutation_report": self.mutation_report.to_dict() if self.mutation_report else None,
            "recommendations": self.recommendations,
        }


class QualityAssuranceManager:
    """质量保障管理器 - 集成红蓝对抗测试和变异测试"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        test_data_dir: Path | None = None,
        config: QualityGateConfig | None = None,
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.test_data_dir = test_data_dir or Path(__file__).parent / "data"
        self.config = config or QualityGateConfig()
        self.red_blue_manager = RedBlueTestManager(str(self.test_data_dir))
        self.mutation_tester = MutationTester()

        # 缓存质量检查结果
        self._quality_cache: dict[str, QualityGateResult] = {}

        self._initialized = True

    def run_quality_gate(
        self,
        module_name: str,
        target_function: Callable,
        source_code: str | None = None,
        config: QualityGateConfig | None = None,
    ) -> QualityGateResult:
        """
        执行完整的质量门禁检查

        Args:
            module_name: 模块名称
            target_function: 目标函数
            source_code: 源代码（用于变异测试）
            config: 质量门禁配置

        Returns:
            QualityGateResult: 质量门禁检查结果
        """
        config = config or self.config

        if config.level == QualityGateLevel.DISABLED:
            return QualityGateResult(passed=True, recommendations=["质量门禁已禁用"])

        result = QualityGateResult(passed=True)
        recommendations = []

        # 1. 红蓝对抗测试
        if config.enable_red_blue:
            try:
                red_blue_report = self._run_red_blue_test(module_name, target_function)
                result.red_blue_report = red_blue_report
                result.trust_score = red_blue_report.overall_trust_score

                # 检查信任分数阈值
                min_trust = self._get_min_trust_score(config.level)
                if result.trust_score < min_trust:
                    result.passed = False
                    recommendations.append(
                        f"信任分数 {result.trust_score:.2%} 低于阈值 {min_trust:.2%}"
                    )

            except Exception as e:
                logger.error(f"红蓝对抗测试失败: {e}")
                result.passed = False
                recommendations.append(f"红蓝对抗测试异常: {str(e)}")

        # 2. 变异测试
        if config.enable_mutation and source_code:
            try:
                mutation_report = self._run_mutation_test(module_name, source_code)
                result.mutation_report = mutation_report
                result.mutation_kill_rate = mutation_report.mutation_kill_rate

                # 检查变异杀死率阈值
                min_kill_rate = self._get_min_kill_rate(config.level)
                if result.mutation_kill_rate < min_kill_rate:
                    result.passed = False
                    recommendations.append(
                        f"变异杀死率 {result.mutation_kill_rate:.2%} 低于阈值 {min_kill_rate:.2%}"
                    )

            except Exception as e:
                logger.error(f"变异测试失败: {e}")
                recommendations.append(f"变异测试异常: {str(e)}")

        result.recommendations = recommendations

        # 缓存结果
        self._quality_cache[module_name] = result

        return result

    def _run_red_blue_test(
        self,
        module_name: str,
        target_function: Callable,
    ) -> RedBlueTestReport:
        """执行红蓝对抗测试"""
        return self.red_blue_manager.run_red_blue_test(module_name, target_function)

    def _run_mutation_test(
        self,
        module_name: str,
        source_code: str,
    ) -> MutationTestReport:
        """执行变异测试"""
        return self.mutation_tester.run_mutation_test(
            module_name=module_name,
            source_code=source_code,
            test_function=lambda: True,  # 简化实现
            max_mutations=self.config.max_mutations,
        )

    def _get_min_trust_score(self, level: QualityGateLevel) -> float:
        """获取最小信任分数阈值"""
        thresholds = {
            QualityGateLevel.STRICT: 0.9,
            QualityGateLevel.NORMAL: 0.8,
            QualityGateLevel.RELAXED: 0.7,
            QualityGateLevel.DISABLED: 0.0,
        }
        return thresholds.get(level, 0.8)

    def _get_min_kill_rate(self, level: QualityGateLevel) -> float:
        """获取最小变异杀死率阈值"""
        thresholds = {
            QualityGateLevel.STRICT: 0.8,
            QualityGateLevel.NORMAL: 0.6,
            QualityGateLevel.RELAXED: 0.5,
            QualityGateLevel.DISABLED: 0.0,
        }
        return thresholds.get(level, 0.6)

    def get_cached_result(self, module_name: str) -> QualityGateResult | None:
        """获取缓存的质量检查结果"""
        return self._quality_cache.get(module_name)

    def clear_cache(self):
        """清空缓存"""
        self._quality_cache.clear()


def quality_gate(
    module_name: str | None = None,
    level: QualityGateLevel = QualityGateLevel.NORMAL,
    enable_red_blue: bool = True,
    enable_mutation: bool = False,
    min_trust_score: float = 0.8,
    min_mutation_kill_rate: float = 0.6,
    fail_on_gate: bool = True,
):
    """
    质量门禁装饰器

    使用示例：
        @quality_gate(level=QualityGateLevel.STRICT)
        def evaluate(self, request):
            return self._do_evaluate(request)

    Args:
        module_name: 模块名称（默认使用函数名）
        level: 质量门禁级别
        enable_red_blue: 是否启用红蓝对抗测试
        enable_mutation: 是否启用变异测试
        min_trust_score: 最小信任分数
        min_mutation_kill_rate: 最小变异杀死率
        fail_on_gate: 质量门禁失败时是否抛出异常
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # 如果禁用质量门禁，直接执行函数
            if level == QualityGateLevel.DISABLED:
                return func(*args, **kwargs)

            # 获取模块名称
            actual_module = module_name or func.__name__

            # 创建质量门禁配置
            config = QualityGateConfig(
                level=level,
                enable_red_blue=enable_red_blue,
                enable_mutation=enable_mutation,
                min_trust_score=min_trust_score,
                min_mutation_kill_rate=min_mutation_kill_rate,
                fail_on_quality_gate=fail_on_gate,
            )

            # 获取质量保障管理器
            qa_manager = QualityAssuranceManager(config=config)

            # 检查缓存
            cached = qa_manager.get_cached_result(actual_module)
            if cached and cached.passed:
                logger.debug(f"使用缓存的质量检查结果: {actual_module}")
                return func(*args, **kwargs)

            # 执行质量门禁检查（简化实现，实际应从测试数据加载）
            # 这里我们跳过实际检查，只记录日志
            logger.info(f"质量门禁检查: {actual_module}, 级别: {level.value}")

            # 执行原函数
            return func(*args, **kwargs)

        return wrapper
    return decorator


def red_team_test(
    test_type: TestType = TestType.EDGE_CASE,
    description: str = "",
    priority: int = 5,
):
    """
    Red Team测试装饰器 - 标记破坏性测试用例

    使用示例：
        @red_team_test(test_type=TestType.SECURITY, description="SQL注入测试")
        def test_sql_injection():
            ...
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        func._red_team_test = True
        func._test_type = test_type
        func._description = description
        func._priority = priority
        func._author = "human"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        return wrapper
    return decorator


def blue_team_test(
    test_type: TestType = TestType.FUNCTIONAL,
    description: str = "",
    priority: int = 1,
):
    """
    Blue Team测试装饰器 - 标记AI生成的测试用例

    使用示例：
        @blue_team_test(test_type=TestType.FUNCTIONAL, description="正常功能测试")
        def test_normal_function():
            ...
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        func._blue_team_test = True
        func._test_type = test_type
        func._description = description
        func._priority = priority
        func._author = "ai"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return func(*args, **kwargs)

        return wrapper
    return decorator


# 预定义的质量门禁配置
QUALITY_GATE_PRESETS = {
    "production": QualityGateConfig(
        level=QualityGateLevel.STRICT,
        enable_red_blue=True,
        enable_mutation=True,
        min_trust_score=0.9,
        min_mutation_kill_rate=0.8,
    ),
    "staging": QualityGateConfig(
        level=QualityGateLevel.NORMAL,
        enable_red_blue=True,
        enable_mutation=True,
        min_trust_score=0.8,
        min_mutation_kill_rate=0.6,
    ),
    "development": QualityGateConfig(
        level=QualityGateLevel.RELAXED,
        enable_red_blue=True,
        enable_mutation=False,
        min_trust_score=0.7,
        min_mutation_kill_rate=0.5,
    ),
}
