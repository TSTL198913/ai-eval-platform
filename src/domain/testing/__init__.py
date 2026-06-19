"""
AI代码产出质量保障测试模块

核心原则：信任但验证（Trust, but verify）

模块组成：
1. red_blue_testing: 红蓝对抗测试
   - Blue Team: AI生成的代码 + AI生成的测试
   - Red Team: 人类编写的破坏性测试
   
2. mutation_testing: 变异测试
   - 在业务代码中引入微小缺陷
   - 检测测试代码是否有效
   
3. quality_gates: 质量门禁装饰器和集成接口
   - @quality_gate 装饰器
   - QualityAssuranceManager 质量保障管理器
   - 预设配置（production/staging/development）
   
4. chaos_testing: 混沌工程测试（待开发）
   - 注入网络延迟、服务宕机
   - 验证容错代码有效性
   
使用场景：
- 对AI生成的测试代码不信任时
- 验证功能完整性
- CI/CD质量门禁增强
"""

from .red_blue_testing import (
    RedBlueTestManager,
    RedBlueTestReport,
    TestCase,
    TeamRole,
    TestType,
    RedBlueTestResult,
    EXAMPLE_RED_TEST_SUITE,
    EXAMPLE_BLUE_TEST_SUITE,
)

from .mutation_testing import (
    MutationTester,
    MutationTestReport,
    Mutation,
    MutationType,
    MutationOperator,
    MutationTestResult,
)

from .quality_gates import (
    QualityGateLevel,
    QualityGateConfig,
    QualityGateResult,
    QualityAssuranceManager,
    quality_gate,
    red_team_test,
    blue_team_test,
    QUALITY_GATE_PRESETS,
)

__all__ = [
    # 红蓝对抗测试
    "RedBlueTestManager",
    "RedBlueTestReport",
    "RedBlueTestResult",
    "TestCase",
    "TeamRole",
    "TestType",
    "EXAMPLE_RED_TEST_SUITE",
    "EXAMPLE_BLUE_TEST_SUITE",
    # 变异测试
    "MutationTester",
    "MutationTestReport",
    "MutationTestResult",
    "Mutation",
    "MutationType",
    "MutationOperator",
    # 质量门禁
    "QualityGateLevel",
    "QualityGateConfig",
    "QualityGateResult",
    "QualityAssuranceManager",
    "quality_gate",
    "red_team_test",
    "blue_team_test",
    "QUALITY_GATE_PRESETS",
]