from unittest.mock import MagicMock

from src.domain.evaluators.trajectory import TrajectoryEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestTrajectoryEvaluator:
    """轨迹评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()
        self.evaluator = TrajectoryEvaluator(self.mock_client)

    def test_evaluate_record_trajectory(self):
        """测试记录轨迹"""
        request = EvaluationSchema(
            id="case_001",
            type="trajectory",
            payload={
                "action": "record",
                "trajectory_id": "traj_001",
                "model_name": "gpt-4",
                "steps": [
                    {
                        "action": "thought",
                        "thought": "分析问题",
                        "tool_name": "search",
                        "tool_args": {"query": "test"},
                        "tool_result": "result",
                        "token_usage": 100,
                        "latency_ms": 100,
                    }
                ],
                "final_output": "最终答案",
                "success": True,
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert "traj_001" in result.data["trajectory_id"]

    def test_evaluate_replay_trajectory(self):
        """测试轨迹回放"""
        self.test_evaluate_record_trajectory()

        request = EvaluationSchema(
            id="case_001",
            type="trajectory",
            payload={"action": "replay", "trajectory_id": "traj_001"},
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["trajectory_id"] == "traj_001"

    def test_evaluate_replay_nonexistent(self):
        """测试回放不存在的轨迹"""
        request = EvaluationSchema(
            id="case_001",
            type="trajectory",
            payload={"action": "replay", "trajectory_id": "nonexistent"},
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_analyze_trajectory(self):
        """测试轨迹分析"""
        self.test_evaluate_record_trajectory()

        request = EvaluationSchema(
            id="case_001",
            type="trajectory",
            payload={"action": "analyze", "trajectory_id": "traj_001"},
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True
        assert "steps_count" in result.data

    def test_evaluate_analyze_nonexistent(self):
        """测试分析不存在的轨迹"""
        request = EvaluationSchema(
            id="case_001",
            type="trajectory",
            payload={"action": "analyze", "trajectory_id": "nonexistent"},
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_trajectory_default(self):
        """测试默认评估动作"""
        request = EvaluationSchema(
            id="case_001",
            type="trajectory",
            payload={
                "steps": [
                    {"action": "thought", "thought": "思考步骤"},
                    {"action": "tool", "tool_name": "search"},
                ],
                "expected_output": "期望输出",
                "actual_output": "实际输出",
            },
        )

        result = self.evaluator.evaluate(request)

        assert result.is_valid is True

    def test_perform_analysis_empty_trajectory(self):
        """测试分析空轨迹"""
        from src.schemas.evaluation import AgentTrajectory

        trajectory = AgentTrajectory(trajectory_id="empty", case_id="test", model_name="test")
        analysis = self.evaluator._perform_analysis(trajectory)

        assert analysis["steps_count"] == 0
        assert analysis["overall_score"] == 0.25

    def test_list_trajectories(self):
        """测试列出轨迹"""
        self.test_evaluate_record_trajectory()
        trajectories = self.evaluator.list_trajectories()

        assert "traj_001" in trajectories