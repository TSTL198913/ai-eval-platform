from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.trajectory import TrajectoryEvaluator
from src.schemas.evaluation import AgentTrajectory, EvaluationSchema, TrajectoryStep


class TestDecisionPathValidation:
    """决策路径验证测试"""

    def setup_method(self):
        self.mock_client = MagicMock()
        self.evaluator = TrajectoryEvaluator(self.mock_client)

    def test_validate_decision_path_with_expected_path(self):
        """测试验证决策路径与期望路径匹配"""
        request = EvaluationSchema(
            id="case_001",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "expected_path": ["analyze", "search", "summarize"],
                "steps": [
                    {"action": "analyze", "thought": "分析问题目标"},
                    {"action": "search", "thought": "搜索相关信息"},
                    {"action": "summarize", "thought": "总结结果"},
                ],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["path_validity"]["score"] == 1.0
        assert result.data["overall_score"] >= 0.5

    def test_validate_decision_path_partial_match(self):
        """测试决策路径部分匹配"""
        request = EvaluationSchema(
            id="case_002",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "expected_path": ["analyze", "search", "summarize", "finish"],
                "steps": [
                    {"action": "analyze", "thought": "分析问题"},
                    {"action": "search", "thought": "搜索信息"},
                    {"action": "finish", "thought": "完成任务"},
                ],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert 0.0 < result.data["path_validity"]["score"] < 1.0

    def test_validate_decision_path_no_expected_path(self):
        """测试无期望路径的决策验证"""
        request = EvaluationSchema(
            id="case_003",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "steps": [
                    {"action": "analyze", "thought": "分析问题"},
                    {"action": "search", "thought": "搜索信息"},
                ],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["path_validity"]["score"] == 0.5

    def test_validate_decision_path_no_steps(self):
        """测试无步骤数据的决策验证"""
        request = EvaluationSchema(
            id="case_004",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "expected_path": ["analyze", "search"],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_validate_decision_path_with_recorded_trajectory(self):
        """测试使用已记录轨迹进行决策验证"""
        record_request = EvaluationSchema(
            id="case_005",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj_decision",
                "steps": [
                    {"action": "analyze", "thought": "分析问题"},
                    {"action": "search", "thought": "搜索信息"},
                    {"action": "summarize", "thought": "总结结果"},
                ],
            },
        )
        self.evaluator.evaluate(record_request)

        validate_request = EvaluationSchema(
            id="case_005",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "trajectory_id": "traj_decision",
                "expected_path": ["analyze", "search", "summarize"],
            },
        )

        result = self.evaluator.evaluate(validate_request)

        assert result.is_valid is True
        assert result.data["actual_actions"] == ["analyze", "search", "summarize"]

    def test_check_logical_coherence_with_coherent_steps(self):
        """测试逻辑连贯性检查（连贯）"""
        steps = [
            TrajectoryStep(step_id="1", action="search", tool_name="search", tool_result="found info", timestamp=1.0),
            TrajectoryStep(step_id="2", action="analyze", thought="根据search结果分析", timestamp=2.0),
        ]

        result = self.evaluator._check_logical_coherence(steps)

        assert result["score"] == 1.0
        assert result["coherent_pairs"] == 1

    def test_check_logical_coherence_with_incoherent_steps(self):
        """测试逻辑连贯性检查（不连贯）"""
        steps = [
            TrajectoryStep(step_id="1", action="search", tool_name="search", tool_result="found info", timestamp=1.0),
            TrajectoryStep(step_id="2", action="analyze", thought="分析问题", timestamp=2.0),
        ]

        result = self.evaluator._check_logical_coherence(steps)

        assert result["score"] == 0.0
        assert len(result["issues"]) == 1

    def test_check_goal_relevance_with_relevant_steps(self):
        """测试目标相关性检查（相关）"""
        steps = [
            TrajectoryStep(step_id="1", action="analyze", thought="分析任务目标", timestamp=1.0),
            TrajectoryStep(step_id="2", action="search", thought="搜索需要的信息", timestamp=2.0),
            TrajectoryStep(step_id="3", action="summarize", thought="总结答案", timestamp=3.0),
        ]

        result = self.evaluator._check_goal_relevance(steps)

        assert result["score"] == 1.0
        assert result["relevant_steps"] == 3

    def test_check_goal_relevance_with_irrelevant_steps(self):
        """测试目标相关性检查（部分相关）"""
        steps = [
            TrajectoryStep(step_id="1", action="analyze", thought="分析", timestamp=1.0),
            TrajectoryStep(step_id="2", action="random", thought="随便做点什么", timestamp=2.0),
            TrajectoryStep(step_id="3", action="summarize", thought="总结", timestamp=3.0),
        ]

        result = self.evaluator._check_goal_relevance(steps)

        assert result["score"] == 1/3
        assert len(result["irrelevant_steps"]) == 2


class TestSelfReflection:
    """自我反思评估测试"""

    def setup_method(self):
        self.mock_client = MagicMock()
        self.evaluator = TrajectoryEvaluator(self.mock_client)

    def test_self_reflection_with_steps(self):
        """测试自我反思（有步骤）"""
        request = EvaluationSchema(
            id="case_001",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": [
                    {"action": "analyze", "thought": "详细分析问题的各个方面"},
                    {"action": "search", "tool_name": "web_search", "tool_result": "找到信息"},
                    {"action": "summarize", "thought": "总结答案"},
                ],
                "actual_output": "这是最终答案",
                "expected_output": "期望的最终答案",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["steps_analyzed"] == 3
        assert "strengths" in result.data
        assert "weaknesses" in result.data

    def test_self_reflection_with_matching_output(self):
        """测试自我反思（输出匹配）"""
        request = EvaluationSchema(
            id="case_002",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": [
                    {"action": "analyze", "thought": "分析问题"},
                    {"action": "search", "tool_name": "search", "tool_result": "result"},
                ],
                "actual_output": "正确的答案",
                "expected_output": "正确的答案",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["output_similarity"] == 1.0
        assert "输出与期望高度匹配" in result.data["strengths"]

    def test_self_reflection_with_no_steps(self):
        """测试自我反思（无步骤）"""
        request = EvaluationSchema(
            id="case_003",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": [{"action": "start", "thought": "开始"}],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True

    def test_self_reflection_without_expected_output(self):
        """测试自我反思（无期望输出）"""
        request = EvaluationSchema(
            id="case_004",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": [
                    {"action": "analyze", "thought": "分析问题"},
                ],
                "actual_output": "实际输出",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert "output_similarity" not in result.data

    def test_self_reflection_with_recorded_trajectory(self):
        """测试使用已记录轨迹进行自我反思"""
        record_request = EvaluationSchema(
            id="case_005",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj_reflect",
                "steps": [
                    {"action": "analyze", "thought": "分析问题"},
                    {"action": "search", "tool_name": "search", "tool_result": "result"},
                ],
                "final_output": "最终答案",
            },
        )
        self.evaluator.evaluate(record_request)

        reflect_request = EvaluationSchema(
            id="case_005",
            type="trajectory",
            payload={
                "action": "reflect",
                "trajectory_id": "traj_reflect",
                "expected_output": "期望答案",
            },
        )

        result = self.evaluator.evaluate(reflect_request)

        assert result.is_valid is True
        assert result.data["steps_analyzed"] == 2

    def test_perform_reflection_with_tools(self):
        """测试反思（使用工具）"""
        trajectory = AgentTrajectory(trajectory_id="test", case_id="test", model_name="test")
        trajectory.add_step(TrajectoryStep(step_id="1", action="search", tool_name="search", tool_result="result", timestamp=1.0))
        trajectory.final_output = "output"

        reflection = self.evaluator._perform_reflection(trajectory, "expected")

        assert any("成功调用工具search" in s for s in reflection["strengths"])
        assert "未使用任何工具" not in reflection["weaknesses"]

    def test_perform_reflection_without_tools(self):
        """测试反思（未使用工具）"""
        trajectory = AgentTrajectory(trajectory_id="test", case_id="test", model_name="test")
        trajectory.add_step(TrajectoryStep(step_id="1", action="think", thought="思考", timestamp=1.0))
        trajectory.final_output = "output"

        reflection = self.evaluator._perform_reflection(trajectory, "expected")

        assert "未使用任何工具" in reflection["weaknesses"]
        assert any("考虑是否" in s for s in reflection["suggestions"])


class TestThreeTierEvaluation:
    """三层成功标准测试"""

    def setup_method(self):
        self.mock_client = MagicMock()
        self.evaluator = TrajectoryEvaluator(self.mock_client)

    def test_three_tier_evaluate_valid_json(self):
        """测试三层评估（有效JSON）"""
        request = EvaluationSchema(
            id="case_001",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": '{"result": "success", "data": "test"}',
                "expected_output": '{"result": "success", "data": "test"}',
                "format_spec": {"type": "json"},
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["tier1"]["score"] == 1.0
        assert result.data["tier1"]["valid_format"] is True

    def test_three_tier_evaluate_invalid_json(self):
        """测试三层评估（无效JSON）"""
        request = EvaluationSchema(
            id="case_002",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "{invalid json}",
                "expected_output": '{"result": "success"}',
                "format_spec": {"type": "json"},
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["tier1"]["score"] == 0.0
        assert any("JSON格式错误" in e for e in result.data["tier1"]["errors"])

    def test_three_tier_evaluate_markdown_format(self):
        """测试三层评估（Markdown格式）"""
        request = EvaluationSchema(
            id="case_003",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "# 标题\n\n- 列表项1\n- 列表项2",
                "expected_output": "# 标题\n\n- 列表项1",
                "format_spec": {"type": "markdown"},
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["tier1"]["score"] == 1.0

    def test_three_tier_evaluate_semantic_high_similarity(self):
        """测试三层评估（语义高相似度）"""
        request = EvaluationSchema(
            id="case_004",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "这是一个非常详细的回答，包含所有必要的信息。",
                "expected_output": "这是一个详细的回答，包含必要的信息。",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["tier2"]["similarity"] > 0.7
        assert result.data["tier2"]["relevant"] is True

    def test_three_tier_evaluate_goal_achieved(self):
        """测试三层评估（目标达成）"""
        request = EvaluationSchema(
            id="case_005",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "答案是42，这是通过计算得到的结果。",
                "expected_output": '"42"',
                "steps": [{"action": "calculate"}, {"action": "summarize"}],
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["tier3"]["goal_achieved"] is True

    def test_three_tier_evaluate_empty_output(self):
        """测试三层评估（空输出）"""
        request = EvaluationSchema(
            id="case_006",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "",
                "expected_output": "期望输出",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_evaluate_l1_syntax_empty(self):
        """测试L1语法层评估（空输出）"""
        score, details = self.evaluator._evaluate_l1_syntax("", {})

        assert score == 0.0
        assert details["valid_format"] is False

    def test_evaluate_l2_semantic_no_expected(self):
        """测试L2语义层评估（无期望输出）"""
        score, details = self.evaluator._evaluate_l2_semantic("实际输出", None)

        assert score == 0.5
        assert details["relevant"] is True

    def test_evaluate_l3_goal_no_expected(self):
        """测试L3目标层评估（无期望输出）"""
        score, details = self.evaluator._evaluate_l3_goal("实际输出", None)

        assert score == 0.5
        assert details["goal_achieved"] is False