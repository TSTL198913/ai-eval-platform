"""TrajectoryEvaluator 单元测试"""

import pytest
from unittest.mock import MagicMock

from src.domain.evaluators.trajectory import TrajectoryEvaluator
from src.schemas.evaluation import EvaluationSchema
from src.schemas.evaluation import EvaluatorStatus


class TestTrajectoryEvaluatorPositiveCases:
    """正向测试用例"""

    def test_record_trajectory(self):
        """记录轨迹"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_001",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj_001",
                "model_name": "test_model",
                "steps": [
                    {"action": "think", "thought": "思考步骤1"},
                    {"action": "tool", "tool_name": "search", "tool_result": "搜索结果"},
                ],
                "final_output": "最终输出",
                "success": True,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0
        assert response.data["trajectory_id"] == "traj_001"
        assert response.data["steps_count"] == 2

    def test_replay_trajectory(self):
        """回放轨迹"""
        evaluator = TrajectoryEvaluator()
        evaluator.trajectories["traj_002"] = MagicMock()
        evaluator.trajectories["traj_002"].trajectory_id = "traj_002"
        evaluator.trajectories["traj_002"].case_id = "test_case_002"
        evaluator.trajectories["traj_002"].model_name = "test_model"
        evaluator.trajectories["traj_002"].steps = []
        evaluator.trajectories["traj_002"].total_tokens = 100
        evaluator.trajectories["traj_002"].total_latency_ms = 500
        evaluator.trajectories["traj_002"].final_output = "测试输出"
        evaluator.trajectories["traj_002"].success = True

        request = EvaluationSchema(
            id="test_case_002",
            type="trajectory",
            payload={
                "action": "replay",
                "trajectory_id": "traj_002",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0

    def test_analyze_trajectory(self):
        """分析轨迹"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_003",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj_003",
                "steps": [
                    {"action": "think", "thought": "思考"},
                    {"action": "tool", "tool_name": "calc", "tool_result": "result"},
                ],
                "final_output": "输出",
                "success": True,
            },
        )
        evaluator.safe_evaluate(request)

        analyze_request = EvaluationSchema(
            id="test_case_003_analyze",
            type="trajectory",
            payload={
                "action": "analyze",
                "trajectory_id": "traj_003",
            },
        )
        response = evaluator.safe_evaluate(analyze_request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "overall_score" in response.data

    def test_evaluate_trajectory(self):
        """评估轨迹"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_004",
            type="trajectory",
            payload={
                "action": "evaluate",
                "steps": [
                    {"action": "think", "thought": "思考步骤"},
                    {"action": "finish", "thought": "完成"},
                ],
                "expected_output": "期望输出",
                "actual_output": "期望输出",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score > 0.5

    def test_validate_decision_path(self):
        """验证决策路径"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_005",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "steps": [
                    {"action": "think", "thought": "思考"},
                    {"action": "tool", "tool_name": "search", "thought": "基于搜索结果"},
                    {"action": "finish", "thought": "完成"},
                ],
                "expected_path": ["think", "tool", "finish"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "path_validity" in response.data
        assert "logical_coherence" in response.data

    def test_self_reflection(self):
        """自我反思"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_006",
            type="trajectory",
            payload={
                "action": "reflect",
                "steps": [
                    {"action": "think", "thought": "详细的思考过程"},
                    {"action": "tool", "tool_name": "search", "tool_result": "结果"},
                ],
                "actual_output": "实际输出",
                "expected_output": "期望输出",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "reflection_score" in response.data

    def test_three_tier_evaluate(self):
        """三层成功标准评估"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_007",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "有效的输出内容",
                "expected_output": "期望的输出内容",
                "format_spec": {"type": "text"},
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "tier1" in response.data
        assert "tier2" in response.data
        assert "tier3" in response.data

    def test_validate_reasoning_chain(self):
        """验证推理链"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_008",
            type="trajectory",
            payload={
                "action": "validate_reasoning_chain",
                "steps": [
                    {"action": "thought", "thought": "首先分析问题"},
                    {"action": "tool", "tool_name": "search", "tool_result": "搜索结果"},
                    {"action": "thought", "thought": "基于搜索结果得出结论"},
                    {"action": "finish", "thought": "完成任务"},
                ],
                "goal_description": "分析问题并得出结论",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "chain_validity" in response.data
        assert "circular_reasoning" in response.data


class TestTrajectoryEvaluatorNegativeCases:
    """负向测试用例"""

    def test_record_trajectory_without_id(self):
        """记录轨迹缺少 ID"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_009",
            type="trajectory",
            payload={
                "action": "record",
                "steps": [],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "trajectory_id" in response.error

    def test_replay_nonexistent_trajectory(self):
        """回放不存在的轨迹"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_010",
            type="trajectory",
            payload={
                "action": "replay",
                "trajectory_id": "nonexistent",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "不存在" in response.error

    def test_analyze_nonexistent_trajectory(self):
        """分析不存在的轨迹"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_011",
            type="trajectory",
            payload={
                "action": "analyze",
                "trajectory_id": "nonexistent",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_three_tier_evaluate_without_output(self):
        """三层评估缺少输出"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_012",
            type="trajectory",
            payload={
                "action": "three_tier_evaluate",
                "actual_output": "",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "actual_output" in response.error

    def test_validate_reasoning_chain_without_steps(self):
        """验证推理链缺少步骤时应返回有效响应"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_013",
            type="trajectory",
            payload={
                "action": "validate_reasoning_chain",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response is not None
        assert response.evaluation_status in [EvaluatorStatus.SUCCESS, EvaluatorStatus.ERROR, EvaluatorStatus.PARTIAL]
        assert response.error is not None or response.score is not None

    def test_reflect_without_steps(self):
        """反思缺少步骤时应返回有效响应"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_014",
            type="trajectory",
            payload={
                "action": "reflect",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response is not None
        assert response.evaluation_status in [EvaluatorStatus.SUCCESS, EvaluatorStatus.ERROR, EvaluatorStatus.PARTIAL]
        assert response.error is not None or response.score is not None


class TestTrajectoryEvaluatorBoundaryCases:
    """边界测试用例"""

    def test_empty_steps(self):
        """空步骤"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_015",
            type="trajectory",
            payload={
                "action": "evaluate",
                "steps": [],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS

    def test_single_step_trajectory(self):
        """单步骤轨迹"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_016",
            type="trajectory",
            payload={
                "action": "evaluate",
                "steps": [{"action": "finish", "thought": "直接完成"}],
                "expected_output": "输出",
                "actual_output": "输出",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS

    def test_validate_decision_path_without_expected(self):
        """验证决策路径无期望路径"""
        evaluator = TrajectoryEvaluator()
        request = EvaluationSchema(
            id="test_case_017",
            type="trajectory",
            payload={
                "action": "validate_decision_path",
                "steps": [{"action": "think"}],
                "expected_path": [],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "path_validity" in response.data

    def test_large_number_of_steps(self):
        """大量步骤"""
        evaluator = TrajectoryEvaluator()
        steps = [{"action": "think", "thought": f"思考{i}"} for i in range(20)]
        request = EvaluationSchema(
            id="test_case_018",
            type="trajectory",
            payload={
                "action": "evaluate",
                "steps": steps,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS


class TestTrajectoryEvaluatorIntegration:
    """集成测试用例"""

    def test_evaluator_registered_in_factory(self):
        """评估器应在工厂中注册"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        assert "trajectory" in EvaluatorFactory._registry

    def test_clear_data(self):
        """清空数据"""
        evaluator = TrajectoryEvaluator()
        evaluator.trajectories["test"] = MagicMock()
        evaluator.clear_data()
        assert len(evaluator.trajectories) == 0

    def test_list_trajectories(self):
        """列出轨迹"""
        evaluator = TrajectoryEvaluator()
        evaluator.trajectories["traj1"] = MagicMock()
        evaluator.trajectories["traj2"] = MagicMock()
        trajectories = evaluator.list_trajectories()
        assert len(trajectories) == 2
        assert "traj1" in trajectories
