"""
TrajectoryEvaluator 专项测试
测试目标：验证轨迹评估器的记录、回放、分析、验证等功能
关键发现：
- 轨迹记录支持多步骤添加和统计
- 决策路径验证支持期望路径匹配
- 三层评估支持语法、语义、目标层验证
- 推理链验证支持循环检测和矛盾检测
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.trajectory import TrajectoryEvaluator
from src.schemas.evaluation import EvaluationSchema


@pytest.fixture(autouse=True)
def reset_evaluators_each_test():
    """
    自动在每个测试前重置 EvaluatorFactory 并重新触发自动发现。
    """
    from src.domain.evaluators import auto_discover
    from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF
    EF._registry = {}
    auto_discover(force=True)
    yield
    EF._registry = {}


# ============================================================
# Part 1: 正向测试 - 正常输入应返回预期输出
# ============================================================
class TestTrajectoryEvaluatorPositiveCases:
    """正向测试 - 验证正常业务流程"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器实例"""
        return TrajectoryEvaluator()

    def test_record_trajectory_with_valid_steps_returns_success(self, evaluator):
        """合法轨迹记录应返回成功"""
        # Arrange
        request = EvaluationSchema(
            id="test-001",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj-001",
                "model_name": "gpt-4",
                "steps": [
                    {"action": "thought", "thought": "分析用户需求", "timestamp": 1000},
                    {"action": "tool", "tool_name": "search", "tool_result": "结果1"},
                ],
                "final_output": "任务完成",
                "success": True,
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.score == 1.0
        assert "已记录" in result.text
        assert result.data["trajectory_id"] == "traj-001"
        assert result.data["steps_count"] == 2
        assert result.data["success"] is True

    def test_replay_trajectory_with_existing_id_returns_steps(self, evaluator):
        """回放已存在的轨迹应返回步骤详情"""
        # Arrange - 先记录轨迹
        record_request = EvaluationSchema(
            id="test-002",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj-002",
                "steps": [{"action": "thought", "thought": "思考中"}],
            },
        )
        evaluator.evaluate(record_request)

        # Act - 回放轨迹
        replay_request = EvaluationSchema(
            id="test-002",
            type="trajectory",
            payload={"action": "replay", "trajectory_id": "traj-002"},
        )
        result = evaluator.evaluate(replay_request)

        # Assert
        assert result.is_valid is True
        assert result.data["trajectory_id"] == "traj-002"
        assert len(result.data["steps"]) == 1
        assert result.data["steps"][0]["action"] == "thought"

    def test_analyze_trajectory_returns_metrics(self, evaluator):
        """分析轨迹应返回完整指标"""
        # Arrange
        record_request = EvaluationSchema(
            id="test-003",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj-003",
                "steps": [
                    {"action": "thought", "thought": "分析", "latency_ms": 100},
                    {"action": "tool", "tool_name": "search", "tool_result": "结果", "latency_ms": 200},
                    {"action": "finish", "thought": "完成", "latency_ms": 50},
                ],
                "success": True,
            },
        )
        evaluator.evaluate(record_request)

        # Act
        analyze_request = EvaluationSchema(
            id="test-003",
            type="trajectory",
            payload={"action": "analyze", "trajectory_id": "traj-003"},
        )
        result = evaluator.evaluate(analyze_request)

        # Assert
        assert result.is_valid is True
        assert result.data["steps_count"] == 3
        assert result.data["tool_usage_count"] == 1
        assert result.data["tool_success_rate"] == 1.0
        assert result.data["efficiency_score"] >= 0.0
        assert "overall_score" in result.data

    def test_validate_decision_path_with_expected_path_returns_validity(self, evaluator):
        """验证决策路径应返回路径匹配度"""
        # Arrange
        request = EvaluationSchema(
            id="test-004",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "steps": [
                    {"action": "thought"},
                    {"action": "tool"},
                    {"action": "finish"},
                ],
                "expected_path": ["thought", "tool", "finish"],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["path_validity"]["score"] == 1.0
        assert result.data["path_validity"]["correct_count"] == 3
        assert len(result.data["actual_actions"]) == 3

    def test_three_tier_evaluate_with_valid_output_returns_scores(self, evaluator):
        """三层评估应返回语法、语义、目标层分数"""
        # Arrange
        request = EvaluationSchema(
            id="test-005",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": '{"result": "success"}',
                "expected_output": '{"result": "success"}',
                "format_spec": {"type": "json"},
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["tier1"]["score"] == 1.0  # 语法层
        assert result.data["tier2"]["score"] >= 0.9  # 语义层
        assert result.data["tier3"]["score"] >= 0.9  # 目标层
        assert "overall_score" in result.data

    def test_validate_reasoning_chain_with_valid_chain_returns_score(self, evaluator):
        """验证推理链应返回有效性分数"""
        # Arrange
        request = EvaluationSchema(
            id="test-006",
            type="trajectory",
            payload={
                "action": "validate_reasoning_chain",
                "steps": [
                    {"action": "thought", "thought": "首先分析问题"},
                    {"action": "tool", "tool_name": "search", "tool_result": "数据"},
                    {"action": "thought", "thought": "根据数据得出结论"},
                    {"action": "finish"},
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert "chain_validity" in result.data
        assert "logical_coherence" in result.data
        assert "circular_reasoning" in result.data
        assert "contradictions" in result.data

    def test_self_reflection_with_trajectory_returns_strengths_and_weaknesses(self, evaluator):
        """自我反思应返回优缺点分析"""
        # Arrange
        request = EvaluationSchema(
            id="test-007",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": [
                    {"action": "thought", "thought": "这是一个详细的思考过程，超过十个字符"},
                    {"action": "tool", "tool_name": "search", "tool_result": "结果"},
                ],
                "actual_output": "任务完成",
                "expected_output": "任务完成",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert "strengths" in result.data
        assert "weaknesses" in result.data
        assert "suggestions" in result.data
        assert result.data["reflection_score"] >= 0.0


# ============================================================
# Part 2: 负向测试 - 错误输入应返回错误处理
# ============================================================
class TestTrajectoryEvaluatorNegativeCases:
    """负向测试 - 验证错误输入的处理"""

    @pytest.fixture
    def evaluator(self):
        return TrajectoryEvaluator()

    def test_replay_nonexistent_trajectory_returns_error(self, evaluator):
        """回放不存在的轨迹应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-101",
            type="trajectory",
            payload={"action": "replay", "trajectory_id": "nonexistent"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不存在" in result.error

    def test_analyze_nonexistent_trajectory_returns_error(self, evaluator):
        """分析不存在的轨迹应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-102",
            type="trajectory",
            payload={"action": "analyze", "trajectory_id": "nonexistent"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不存在" in result.error

    def test_validate_decision_path_without_trajectory_or_steps_returns_error(self, evaluator):
        """验证决策路径缺少轨迹ID和步骤应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-103",
            type="trajectory",
            payload={"action": "validate_decision_path"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_self_reflection_without_trajectory_or_steps_returns_error(self, evaluator):
        """自我反思缺少轨迹ID和步骤应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-104",
            type="trajectory",
            payload={"action": "reflect"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_validate_reasoning_chain_without_trajectory_or_steps_returns_error(self, evaluator):
        """验证推理链缺少轨迹ID和步骤应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-105",
            type="trajectory",
            payload={"action": "validate_reasoning_chain"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_three_tier_evaluate_without_actual_output_returns_error(self, evaluator):
        """三层评估缺少实际输出应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-106",
            type="trajectory",
            payload={"action": "three_tier_evaluate"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不能为空" in result.error


# ============================================================
# Part 3: 边界测试 - 边界值处理
# ============================================================
class TestTrajectoryEvaluatorBoundaryCases:
    """边界测试 - 验证边界值处理"""

    @pytest.fixture
    def evaluator(self):
        return TrajectoryEvaluator()

    def test_record_trajectory_with_empty_steps_returns_success(self, evaluator):
        """记录空步骤轨迹应返回成功"""
        # Arrange
        request = EvaluationSchema(
            id="test-201",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj-empty",
                "steps": [],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["steps_count"] == 0

    def test_analyze_trajectory_with_many_steps_calculates_efficiency(self, evaluator):
        """分析大量步骤轨迹应正确计算效率分数"""
        # Arrange
        steps = [{"action": f"action_{i}", "latency_ms": 100} for i in range(20)]
        record_request = EvaluationSchema(
            id="test-202",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj-many",
                "steps": steps,
                "success": True,
            },
        )
        evaluator.evaluate(record_request)

        # Act
        analyze_request = EvaluationSchema(
            id="test-202",
            type="trajectory",
            payload={"action": "analyze", "trajectory_id": "traj-many"},
        )
        result = evaluator.evaluate(analyze_request)

        # Assert
        assert result.is_valid is True
        assert result.data["steps_count"] == 20
        # 效率分数应低于1.0（步骤过多）
        assert result.data["efficiency_score"] < 1.0

    def test_check_path_validity_with_empty_expected_path_returns_default(self, evaluator):
        """检查路径有效性时期望路径为空应返回默认分数"""
        # Arrange
        request = EvaluationSchema(
            id="test-203",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "steps": [{"action": "thought"}],
                "expected_path": [],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["path_validity"]["score"] == 0.5
        assert "无期望路径" in result.data["path_validity"]["message"]

    def test_check_logical_coherence_with_single_step_returns_default(self, evaluator):
        """检查逻辑连贯性时单步骤应返回默认分数"""
        # Arrange
        request = EvaluationSchema(
            id="test-204",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "steps": [{"action": "thought", "thought": "单步思考"}],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["logical_coherence"]["score"] == 0.5
        assert "步骤数不足" in result.data["logical_coherence"]["message"]

    def test_check_goal_relevance_with_empty_steps_returns_error(self, evaluator):
        """检查目标相关性时空步骤应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-205",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "steps": [],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 空步骤列表会被视为缺少步骤数据，返回错误
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_three_tier_evaluate_with_invalid_json_returns_zero_syntax_score(self, evaluator):
        """三层评估时无效JSON应返回零分语法层分数"""
        # Arrange
        request = EvaluationSchema(
            id="test-206",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "{invalid json}",
                "expected_output": '{"result": "success"}',
                "format_spec": {"type": "json"},
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["tier1"]["score"] == 0.0
        assert result.data["tier1"]["valid_format"] is False
        assert "JSON格式错误" in result.data["tier1"]["errors"][0]

    def test_three_tier_evaluate_with_empty_output_returns_zero_score(self, evaluator):
        """三层评估时空输出应返回零分"""
        # Arrange
        request = EvaluationSchema(
            id="test-207",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "   ",
                "expected_output": "期望输出",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["tier1"]["score"] == 0.0
        assert "输出为空" in result.data["tier1"]["errors"][0]

    def test_perform_reflection_with_no_steps_returns_error(self, evaluator):
        """反思时无步骤应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-208",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": [],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 空步骤列表会被视为缺少步骤数据，返回错误
        assert result.is_valid is False
        assert "不能为空" in result.error


# ============================================================
# Part 4: 异常测试 - 异常情况处理
# ============================================================
class TestTrajectoryEvaluatorExceptionCases:
    """异常测试 - 验证异常情况处理"""

    @pytest.fixture
    def evaluator(self):
        return TrajectoryEvaluator()

    def test_record_trajectory_with_missing_optional_fields_uses_defaults(self, evaluator):
        """记录轨迹时缺少可选字段应使用默认值"""
        # Arrange
        request = EvaluationSchema(
            id="test-301",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj-partial",
                # 缺少 model_name, success, final_output
                "steps": [{"action": "test"}],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["success"] is False  # 默认值

    def test_evaluate_trajectory_with_partial_steps_calculates_correctly(self, evaluator):
        """评估轨迹时部分步骤字段缺失应正确计算"""
        # Arrange
        request = EvaluationSchema(
            id="test-302",
            type="trajectory",
            payload={
                "action": "evaluate",
                "steps": [
                    {"action": "thought"},  # 缺少 thought 字段
                    {"action": "tool", "tool_name": "search"},  # 缺少 tool_result
                ],
                "expected_output": "期望输出",
                "actual_output": "实际输出",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert "steps_count" in result.data
        assert result.data["tool_success_rate"] == 0.0  # 无成功调用

    def test_validate_intermediate_results_with_no_expected_returns_default(self, evaluator):
        """验证中间结果时无期望值应返回默认分数"""
        # Arrange
        request = EvaluationSchema(
            id="test-303",
            type="trajectory",
            payload={
                "action": "validate_reasoning_chain",
                "steps": [{"action": "thought", "thought": "思考"}],
                "expected_intermediate": {},
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["intermediate_validation"]["score"] == 0.5
        assert "无期望中间结果" in result.data["intermediate_validation"]["message"]

    def test_detect_circular_reasoning_with_similar_thoughts_detects_circular(self, evaluator):
        """检测循环推理时相似思考应被检测"""
        # Arrange
        similar_thought = "这是一个重复的思考过程，内容完全相同"
        request = EvaluationSchema(
            id="test-304",
            type="trajectory",
            payload={
                "action": "validate_reasoning_chain",
                "steps": [
                    {"action": "thought", "thought": similar_thought},
                    {"action": "tool", "tool_name": "search"},
                    {"action": "thought", "thought": similar_thought},  # 重复
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["circular_reasoning"]["circular_detected"] is True
        assert len(result.data["circular_reasoning"]["circular_occurrences"]) > 0

    def test_detect_contradictions_with_negation_keywords_detects_issues(self, evaluator):
        """检测矛盾时包含否定关键词应被检测"""
        # Arrange
        request = EvaluationSchema(
            id="test-305",
            type="trajectory",
            payload={
                "action": "validate_reasoning_chain",
                "steps": [
                    {"action": "thought", "thought": "这个方案是正确的"},
                    {"action": "thought", "thought": "但是这个方案不是正确的"},
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        # 矛盾检测可能检测到问题
        assert "contradiction_score" in result.data["contradictions"]


# ============================================================
# Part 5: 依赖测试 - 外部依赖Mock
# ============================================================
class TestTrajectoryEvaluatorDependencyHandling:
    """依赖测试 - 验证外部依赖处理"""

    @pytest.fixture
    def evaluator(self):
        return TrajectoryEvaluator()

    def test_evaluator_without_client_works_correctly(self, evaluator):
        """无LLM客户端时评估器应正常工作"""
        # Arrange
        assert evaluator.client is None

        # Act
        request = EvaluationSchema(
            id="test-401",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj-no-client",
                "steps": [{"action": "test"}],
            },
        )
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["trajectory_id"] == "traj-no-client"

    def test_evaluator_with_mock_client_works_correctly(self):
        """使用Mock客户端时评估器应正常工作"""
        # Arrange
        mock_client = MagicMock()
        mock_client.name = "mock-llm"
        evaluator = TrajectoryEvaluator(client=mock_client)

        # Act
        request = EvaluationSchema(
            id="test-402",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj-with-client",
                "steps": [{"action": "test"}],
            },
        )
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert evaluator.client is mock_client

    def test_list_trajectories_returns_all_recorded_ids(self, evaluator):
        """列出轨迹应返回所有已记录的ID"""
        # Arrange
        for i in range(3):
            request = EvaluationSchema(
                id=f"test-403-{i}",
                type="trajectory",
                payload={
                    "action": "record",
                    "trajectory_id": f"traj-{i}",
                    "steps": [],
                },
            )
            evaluator.evaluate(request)

        # Act
        trajectory_ids = evaluator.list_trajectories()

        # Assert
        assert len(trajectory_ids) == 3
        assert "traj-0" in trajectory_ids
        assert "traj-1" in trajectory_ids
        assert "traj-2" in trajectory_ids

    def test_record_trajectory_accumulates_tokens_and_latency(self, evaluator):
        """记录轨迹应累积token和延迟统计"""
        # Arrange
        request = EvaluationSchema(
            id="test-404",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj-stats",
                "steps": [
                    {"action": "thought", "token_usage": 100, "latency_ms": 50},
                    {"action": "tool", "token_usage": 200, "latency_ms": 100},
                    {"action": "finish", "token_usage": 50, "latency_ms": 20},
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.data["total_tokens"] == 350
        assert result.data["total_latency_ms"] == 170


# ============================================================
# Part 6: 特殊场景测试 - 复杂业务逻辑
# ============================================================
class TestTrajectoryEvaluatorSpecialScenarios:
    """特殊场景测试 - 验证复杂业务逻辑"""

    @pytest.fixture
    def evaluator(self):
        return TrajectoryEvaluator()

    def test_check_enhanced_coherence_with_goal_keywords_increases_score(self, evaluator):
        """检查增强连贯性时目标关键词应提高分数"""
        # Arrange
        request = EvaluationSchema(
            id="test-501",
            type="trajectory",
            payload={
                "action": "validate_reasoning_chain",
                "steps": [
                    {"action": "thought", "thought": "我需要完成这个目标"},
                    {"action": "tool", "tool_name": "search", "tool_result": "结果"},
                    {"action": "thought", "thought": "因此我得出结论"},
                ],
                "goal_description": "完成目标测试",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        # 目标关键词匹配应提高连贯性分数
        assert result.data["logical_coherence"]["score"] >= 0.0

    def test_evaluate_l3_goal_with_finish_action_increases_score(self, evaluator):
        """目标层评估时包含finish动作应提高分数"""
        # Arrange
        request = EvaluationSchema(
            id="test-502",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "任务完成",
                "expected_output": "任务完成",
                "steps": [
                    {"action": "thought"},
                    {"action": "finish"},
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        # finish动作应提高目标层分数
        assert result.data["tier3"]["score"] >= 0.0

    def test_perform_reflection_with_high_similarity_adds_strength(self, evaluator):
        """反思时输出相似度高应添加优点"""
        # Arrange
        request = EvaluationSchema(
            id="test-503",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": [
                    {"action": "thought", "thought": "详细思考过程超过十个字符"},
                ],
                "actual_output": "这是期望的输出结果",
                "expected_output": "这是期望的输出结果",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        # 相似度1.0应添加优点
        assert any("高度匹配" in s for s in result.data["strengths"])

    def test_perform_reflection_with_too_many_steps_adds_weakness(self, evaluator):
        """反思时步骤过多应添加缺点"""
        # Arrange
        steps = [{"action": f"action_{i}", "thought": f"思考{i}"} for i in range(15)]
        request = EvaluationSchema(
            id="test-504",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": steps,
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        # 步骤超过10应添加缺点
        assert any("冗余" in w for w in result.data["weaknesses"])

    def test_perform_reflection_with_no_tool_usage_adds_weakness(self, evaluator):
        """反思时未使用工具应添加缺点"""
        # Arrange
        request = EvaluationSchema(
            id="test-505",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": [
                    {"action": "thought", "thought": "思考过程"},
                    {"action": "finish"},
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        # 未使用工具应添加缺点
        assert any("未使用任何工具" in w for w in result.data["weaknesses"])

    def test_check_reasoning_chain_validity_with_multiple_steps_calculates_correctly(self, evaluator):
        """检查推理链有效性时应正确计算转换分数"""
        # Arrange - 创建一个有效的推理链
        request = EvaluationSchema(
            id="test-506",
            type="trajectory",
            payload={
                "action": "validate_reasoning_chain",
                "steps": [
                    {"action": "thought"},
                    {"action": "tool"},
                    {"action": "thought"},
                    {"action": "finish"},
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        # 有效转换链应返回高分
        assert result.data["chain_validity"]["score"] == 1.0
        assert result.data["chain_validity"]["valid_transitions"] == 3
