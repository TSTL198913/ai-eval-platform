"""Trajectory 轨迹评估器

用于记录和评估 Agent 的决策路径、推理链及自我反思能力，包括：
- 轨迹安全记录与回放
- 决策路径目标相关性与逻辑连贯性验证
- 三层成功标准（语法、语义、目标）评估
- 推理链环路（循环论证）与矛盾检测
"""

import json
import logging
import re
import threading
import time
from difflib import SequenceMatcher
from typing import Any

# 假设的基础依赖导入路径
from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import AgentTrajectory, DomainResponse, EvaluationSchema, TrajectoryStep

# 设置日志
logger = logging.getLogger(__name__)

# 模块级预编译正则
_WORD_RE = re.compile(r"\b[a-zA-Z\u4e00-\u9fff]{2,}\b")
_QUOTED_RE = re.compile(r'"([^"]*)"')

# 错误关键词正则
_ERROR_INDICATORS_RE = re.compile(
    r"(error|exception|failed|failure|timeout|timed\s+out|invalid|denied|forbidden|not\s+found|错误|异常|失败|超时|无效|禁止|未找到)",
    re.IGNORECASE,
)


@EvaluatorFactory.register("trajectory")
class TrajectoryEvaluator(BaseEvaluator):
    """Trajectory 轨迹评估器"""

    def __init__(self, client=None):
        super().__init__(client)
        # 并发安全：使用细粒度线程锁保护 trajectories 字典访问
        self._trajectory_lock = threading.Lock()
        self.trajectories: dict[str, AgentTrajectory] = {}

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """评估入口（采用现代 Python 模式匹配 match-case 路由）"""
        action = self.get_payload_data(request, "action", "evaluate")
        trajectory_id = self.get_payload_data(request, "trajectory_id")

        logger.debug(f"TrajectoryEvaluator 正在执行动作: {action}, 轨迹ID: {trajectory_id}")

        match action:
            case "record":
                return self._record_trajectory(request)
            case "replay":
                return self._replay_trajectory(trajectory_id)
            case "analyze":
                return self._analyze_trajectory(request)
            case "validate_decision_path":
                return self._validate_decision_path(request)
            case "reflect":
                return self._self_reflection(request)
            case "three_tier_evaluate":
                return self._three_tier_evaluate(request)
            case "validate_reasoning_chain":
                return self._validate_reasoning_chain(request)
            case _:
                return self._evaluate_trajectory(request)

    def _record_trajectory(self, request: EvaluationSchema) -> DomainResponse:
        """安全记录 Agent 轨迹"""
        trajectory_id = self.get_payload_data(request, "trajectory_id")
        case_id = request.id
        model_name = self.get_payload_data(request, "model_name", "unknown")
        steps_data = self.get_payload_data(request, "steps", [])

        if not trajectory_id:
            return DomainResponse(is_valid=False, error="trajectory_id 不能为空")

        trajectory = AgentTrajectory(
            trajectory_id=trajectory_id,
            case_id=case_id,
            model_name=model_name,
        )

        for i, step_data in enumerate(steps_data):
            step = TrajectoryStep(
                step_id=f"{trajectory_id}-step-{i}",
                action=step_data.get("action", "unknown"),
                thought=step_data.get("thought"),
                observation=step_data.get("observation"),
                tool_name=step_data.get("tool_name"),
                tool_args=step_data.get("tool_args"),
                tool_result=step_data.get("tool_result"),
                timestamp=step_data.get("timestamp", time.time()),
                token_usage=step_data.get("token_usage", 0),
                latency_ms=step_data.get("latency_ms", 0),
            )
            trajectory.add_step(step)

        trajectory.final_output = self.get_payload_data(request, "final_output")
        trajectory.success = self.get_payload_data(request, "success", False)

        with self._trajectory_lock:
            self.trajectories[trajectory_id] = trajectory

        return DomainResponse(
            is_valid=True,
            text=f"轨迹 {trajectory_id} 已成功记录",
            score=1.0,
            data={
                "trajectory_id": trajectory_id,
                "steps_count": len(trajectory.steps),
                "total_tokens": trajectory.total_tokens,
                "total_latency_ms": trajectory.total_latency_ms,
                "success": trajectory.success,
            },
        )

    def _replay_trajectory(self, trajectory_id: str | None) -> DomainResponse:
        """回放指定轨迹"""
        if not trajectory_id:
            return DomainResponse(is_valid=False, error="请求中未提供 trajectory_id")

        with self._trajectory_lock:
            trajectory = self.trajectories.get(trajectory_id)

        if not trajectory:
            return DomainResponse(is_valid=False, error=f"轨迹 {trajectory_id} 不存在")

        return DomainResponse(
            is_valid=True,
            text=f"轨迹 {trajectory_id} 回放数据加载完成",
            score=1.0,
            data={
                "trajectory_id": trajectory.trajectory_id,
                "case_id": trajectory.case_id,
                "model_name": trajectory.model_name,
                "steps": [step.model_dump() for step in trajectory.steps],
                "total_tokens": trajectory.total_tokens,
                "total_latency_ms": trajectory.total_latency_ms,
                "final_output": trajectory.final_output,
                "success": trajectory.success,
            },
        )

    def _analyze_trajectory(self, request: EvaluationSchema) -> DomainResponse:
        """分析指定存盘轨迹性能"""
        trajectory_id = self.get_payload_data(request, "trajectory_id")

        if not trajectory_id:
            return DomainResponse(is_valid=False, error="trajectory_id 不能为空")

        with self._trajectory_lock:
            trajectory = self.trajectories.get(trajectory_id)

        if not trajectory:
            return DomainResponse(is_valid=False, error=f"轨迹 {trajectory_id} 不存在")

        analysis = self._perform_analysis(trajectory)

        return DomainResponse(
            is_valid=True,
            text=f"轨迹 {trajectory_id} 分析完成",
            score=analysis.get("overall_score", 0.5),
            data={"trajectory_id": trajectory_id, **analysis},
        )

    def _evaluate_trajectory(self, request: EvaluationSchema) -> DomainResponse:
        """单次请求式轨迹即时沙盒评估（纯函数，无全局状态污染）"""
        steps_data = self.get_payload_data(request, "steps", [])
        expected_output = self.get_payload_data(request, "expected_output")
        actual_output = self.get_payload_data(request, "actual_output")

        trajectory = AgentTrajectory(
            trajectory_id=f"eval-{request.id}",
            case_id=request.id,
            model_name=self.get_payload_data(request, "model_name", "unknown"),
        )

        for i, step_data in enumerate(steps_data):
            step = TrajectoryStep(
                step_id=f"step-{i}",
                action=step_data.get("action", "unknown"),
                thought=step_data.get("thought"),
                tool_name=step_data.get("tool_name"),
                timestamp=step_data.get("timestamp", time.time()),
            )
            trajectory.add_step(step)

        trajectory.final_output = actual_output
        analysis = self._perform_analysis(trajectory)

        if expected_output and actual_output:
            similarity = SequenceMatcher(None, actual_output, expected_output).ratio()
            analysis["output_similarity"] = similarity
            analysis["overall_score"] = (analysis.get("overall_score", 0.5) + similarity) / 2

        return DomainResponse(
            is_valid=True,
            text="轨迹沙盒评估完成",
            score=analysis.get("overall_score", 0.5),
            data=analysis,
        )

    def _is_tool_result_successful(self, tool_result: str | dict[str, Any] | None) -> bool:
        """【性能暴增点】利用模块级预编译正则判断工具返回是否包含异常指标"""
        if not tool_result:
            return False

        # 正则快速扫描，淘汰原 17 次循环的字符串 match，QPS 产生量级突破并安全防范 ReDoS
        return not bool(_ERROR_INDICATORS_RE.search(str(tool_result)))

    def _perform_analysis(self, trajectory: AgentTrajectory) -> dict[str, Any]:
        """计算轨迹核心健康度指标"""
        steps = trajectory.steps

        tool_usage_count = sum(1 for step in steps if step.tool_name)
        total_thinking_time = sum(step.latency_ms for step in steps)
        avg_step_latency = total_thinking_time / len(steps) if steps else 0.0

        actions = [step.action for step in steps]
        action_variety = len(set(actions)) / len(actions) if actions else 0.0

        tool_success_rate = 0.0
        if tool_usage_count > 0:
            successful_tool_calls = sum(
                1
                for step in steps
                if step.tool_name
                and step.tool_result
                and self._is_tool_result_successful(step.tool_result)
            )
            tool_success_rate = successful_tool_calls / tool_usage_count

        efficiency_score = min(1.0, max(0.0, 1.0 - (len(steps) - 5) * 0.1)) if steps else 0.5

        overall_score = (
            efficiency_score * 0.3
            + tool_success_rate * 0.3
            + action_variety * 0.2
            + (1.0 if trajectory.success else 0.5) * 0.2
        )

        return {
            "steps_count": len(steps),
            "tool_usage_count": tool_usage_count,
            "tool_success_rate": round(tool_success_rate, 4),
            "total_tokens": trajectory.total_tokens,
            "total_latency_ms": trajectory.total_latency_ms,
            "avg_step_latency_ms": round(avg_step_latency, 2),
            "action_variety": round(action_variety, 4),
            "efficiency_score": round(efficiency_score, 4),
            "success": trajectory.success,
            "overall_score": round(overall_score, 4),
        }

    def _validate_decision_path(self, request: EvaluationSchema) -> DomainResponse:
        """验证决策执行路径的贴合度（修复局部变量边界风险）"""
        trajectory_id = self.get_payload_data(request, "trajectory_id")
        expected_path = self.get_payload_data(request, "expected_path", [])
        steps_data = self.get_payload_data(request, "steps", [])

        steps: list[TrajectoryStep] | None = None

        # 优先读取全局并发快照，保障读锁范围紧凑
        if trajectory_id:
            with self._trajectory_lock:
                if trajectory_id in self.trajectories:
                    steps = self.trajectories[trajectory_id].steps

        # 降级方案：若未命中存盘，则从 request 报文中现场构建局部隔离沙盒进行验证
        if steps is None:
            if steps_data:
                local_trajectory = AgentTrajectory(
                    trajectory_id=f"eval-{request.id}",
                    case_id=request.id,
                    model_name=self.get_payload_data(request, "model_name", "unknown"),
                )
                for i, step_data in enumerate(steps_data):
                    local_trajectory.add_step(
                        TrajectoryStep(
                            step_id=f"step-{i}",
                            action=step_data.get("action", "unknown"),
                            thought=step_data.get("thought"),
                            tool_name=step_data.get("tool_name"),
                            timestamp=step_data.get("timestamp", time.time()),
                        )
                    )
                steps = local_trajectory.steps
            else:
                return DomainResponse(
                    is_valid=False, error="无法验证：未找到有效的 trajectory_id 且未传入 steps 数据"
                )

        actual_actions = [step.action for step in steps]
        actual_tools = [step.tool_name for step in steps if step.tool_name]

        path_validity = self._check_path_validity(steps, expected_path)
        logical_coherence = self._check_logical_coherence(steps)
        goal_relevance = self._check_goal_relevance(steps)

        overall_score = (
            path_validity["score"] * 0.4
            + logical_coherence["score"] * 0.3
            + goal_relevance["score"] * 0.3
        )

        return DomainResponse(
            is_valid=True,
            text="决策路径验证完成",
            score=round(overall_score, 4),
            data={
                "trajectory_id": trajectory_id,
                "path_validity": path_validity,
                "logical_coherence": logical_coherence,
                "goal_relevance": goal_relevance,
                "actual_actions": actual_actions,
                "actual_tools": actual_tools,
                "expected_path": expected_path,
                "overall_score": round(overall_score, 4),
            },
        )

    def _check_path_validity(
        self, steps: list[TrajectoryStep], expected_path: list[str]
    ) -> dict[str, Any]:
        if not expected_path:
            return {"score": 0.5, "message": "无期望路径，无法验证", "matches": []}

        actual_actions = [step.action for step in steps]
        matches = []

        for i, expected_action in enumerate(expected_path):
            if i < len(actual_actions):
                is_match = actual_actions[i] == expected_action
                matches.append(
                    {
                        "step": i,
                        "expected": expected_action,
                        "actual": actual_actions[i],
                        "match": is_match,
                    }
                )

        correct_matches = sum(1 for m in matches if m["match"])
        score = correct_matches / len(expected_path) if expected_path else 0.0

        return {
            "score": round(score, 4),
            "matches": matches,
            "correct_count": correct_matches,
            "total_expected": len(expected_path),
        }

    def _check_logical_coherence(self, steps: list[TrajectoryStep]) -> dict[str, Any]:
        if len(steps) < 2:
            return {"score": 0.5, "message": "步骤数不足，无法评估逻辑连贯性"}

        coherence_score = 0.0
        coherence_issues = []

        for i in range(len(steps) - 1):
            current_step = steps[i]
            next_step = steps[i + 1]

            if current_step.tool_result and next_step.thought:
                if current_step.tool_name and current_step.tool_name in str(next_step.thought):
                    coherence_score += 1.0
                else:
                    coherence_issues.append(f"步骤{i}的工具结果未在步骤{i + 1}的思考中体现")

        avg_coherence = coherence_score / (len(steps) - 1) if (len(steps) - 1) > 0 else 0.0

        return {
            "score": round(avg_coherence, 4),
            "issues": coherence_issues,
            "checked_pairs": len(steps) - 1,
            "coherent_pairs": int(coherence_score),
        }

    def _check_goal_relevance(self, steps: list[TrajectoryStep]) -> dict[str, Any]:
        if not steps:
            return {"score": 0.0, "message": "无步骤可评估"}

        relevant_steps = 0
        irrelevant_steps = []
        target_keywords = ("goal", "目标", "objective", "任务", "需要", "应该")

        for i, step in enumerate(steps):
            thought = (step.thought or "").lower()
            if any(kw in thought for kw in target_keywords):
                relevant_steps += 1
            elif step.action in ("finish", "end", "summarize", "总结"):
                relevant_steps += 1
            else:
                irrelevant_steps.append(f"步骤{i}: {step.action}")

        relevance_score = relevant_steps / len(steps)

        return {
            "score": round(relevance_score, 4),
            "relevant_steps": relevant_steps,
            "total_steps": len(steps),
            "irrelevant_steps": irrelevant_steps,
        }

    def _self_reflection(self, request: EvaluationSchema) -> DomainResponse:
        """智能体反思度解算"""
        trajectory_id = self.get_payload_data(request, "trajectory_id")
        steps_data = self.get_payload_data(request, "steps", [])
        actual_output = self.get_payload_data(request, "actual_output")
        expected_output = self.get_payload_data(request, "expected_output")

        trajectory: AgentTrajectory | None = None
        if trajectory_id:
            with self._trajectory_lock:
                trajectory = self.trajectories.get(trajectory_id)

        if trajectory is None:
            if steps_data:
                trajectory = AgentTrajectory(
                    trajectory_id=f"reflect-{request.id}",
                    case_id=request.id,
                    model_name=self.get_payload_data(request, "model_name", "unknown"),
                )
                for i, step_data in enumerate(steps_data):
                    step = TrajectoryStep(
                        step_id=f"step-{i}",
                        action=step_data.get("action", "unknown"),
                        thought=step_data.get("thought"),
                        tool_name=step_data.get("tool_name"),
                        tool_result=step_data.get("tool_result"),
                        timestamp=step_data.get("timestamp", time.time()),
                    )
                    trajectory.add_step(step)
                trajectory.final_output = actual_output
            else:
                return DomainResponse(
                    is_valid=False, error="无法反思：未找到对应的轨迹存档且未传入 steps 报文"
                )

        reflection = self._perform_reflection(trajectory, expected_output)

        return DomainResponse(
            is_valid=True,
            text="自我反思完成",
            score=reflection.get("reflection_score", 0.5),
            data=reflection,
        )

    def _perform_reflection(
        self, trajectory: AgentTrajectory, expected_output: str | None = None
    ) -> dict[str, Any]:
        steps = trajectory.steps
        actual_output = trajectory.final_output

        reflection = {
            "steps_analyzed": len(steps),
            "reflection_score": 0.0,
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }

        if not steps:
            reflection["weaknesses"].append("无执行步骤")
            return reflection

        reflection["strengths"].append(f"完成了{len(steps)}个执行步骤")

        for i, step in enumerate(steps):
            if step.thought:
                if len(str(step.thought)) > 10:
                    reflection["strengths"].append(f"步骤{i}有详细的思考过程")
                else:
                    reflection["weaknesses"].append(f"步骤{i}思考过程过于简略")

            if step.tool_name and step.tool_result:
                reflection["strengths"].append(f"步骤{i}成功调用工具{step.tool_name}")

        if expected_output and actual_output:
            similarity = SequenceMatcher(None, str(actual_output), str(expected_output)).ratio()
            reflection["output_similarity"] = round(similarity, 4)
            if similarity > 0.8:
                reflection["strengths"].append("输出与期望高度匹配")
            elif similarity > 0.5:
                reflection["weaknesses"].append("输出与期望有一定差距")
            else:
                reflection["weaknesses"].append("输出与期望差距较大")

        if len(steps) > 10:
            reflection["weaknesses"].append("步骤过多，可能存在冗余")
            reflection["suggestions"].append("考虑优化执行路径，减少冗余步骤")

        tool_usage = sum(1 for step in steps if step.tool_name)
        if tool_usage == 0:
            reflection["weaknesses"].append("未使用任何工具")
            reflection["suggestions"].append("考虑是否需要使用工具来辅助完成任务")

        raw_score = 0.5 + len(reflection["strengths"]) * 0.1 - len(reflection["weaknesses"]) * 0.05
        reflection["reflection_score"] = round(min(1.0, max(0.0, raw_score)), 4)

        return reflection

    def _three_tier_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """三层成功标准评估"""
        actual_output = self.get_payload_data(request, "actual_output")
        expected_output = self.get_payload_data(request, "expected_output")
        format_spec = self.get_payload_data(request, "format_spec", {})
        steps_data = self.get_payload_data(request, "steps", [])

        if not actual_output:
            return DomainResponse(is_valid=False, error="actual_output 不能为空")

        tier1_score, tier1_details = self._evaluate_l1_syntax(actual_output, format_spec)
        tier2_score, tier2_details = self._evaluate_l2_semantic(actual_output, expected_output)
        tier3_score, tier3_details = self._evaluate_l3_goal(
            actual_output, expected_output, steps_data
        )

        overall_score = tier1_score * 0.25 + tier2_score * 0.35 + tier3_score * 0.4

        return DomainResponse(
            is_valid=True,
            text="三层成功标准评估完成",
            score=round(overall_score, 4),
            data={
                "tier1": {"name": "语法层", "score": tier1_score, **tier1_details},
                "tier2": {"name": "语义层", "score": tier2_score, **tier2_details},
                "tier3": {"name": "目标层", "score": tier3_score, **tier3_details},
                "overall_score": round(overall_score, 4),
            },
        )

    def _evaluate_l1_syntax(
        self, actual_output: str, format_spec: dict[str, Any]
    ) -> tuple[float, dict[str, Any]]:
        details = {"valid_format": True, "errors": []}

        if not actual_output.strip():
            details["valid_format"] = False
            details["errors"].append("输出为空")
            return 0.0, details

        required_format = format_spec.get("type", "")
        match required_format:
            case "json":
                try:
                    json.loads(actual_output)
                except json.JSONDecodeError as e:
                    details["valid_format"] = False
                    details["errors"].append(f"JSON格式错误: {str(e)}")
                    return 0.0, details
            case "markdown":
                if not any(m in actual_output for m in ("#", "*", "**", "- ")):
                    details["valid_format"] = False
                    details["errors"].append("缺少Markdown格式标记")

        return 1.0, details

    def _evaluate_l2_semantic(
        self, actual_output: str, expected_output: str | None = None
    ) -> tuple[float, dict[str, Any]]:
        details = {"relevant": True, "similarity": 0.0}

        if not expected_output:
            return 0.5, details

        similarity = SequenceMatcher(None, actual_output, expected_output).ratio()
        details["similarity"] = round(similarity, 4)

        if similarity > 0.7:
            score = min(1.0, similarity)
        elif similarity > 0.3:
            score = 0.5 + similarity * 0.5
        else:
            details["relevant"] = False
            score = 0.2

        return round(score, 4), details

    def _evaluate_l3_goal(
        self,
        actual_output: str,
        expected_output: str | None = None,
        steps_data: list[dict[str, Any]] | None = None,
    ) -> tuple[float, dict[str, Any]]:
        if steps_data is None:
            steps_data = []
        details = {"goal_achieved": False, "evidence": []}

        if not expected_output:
            return 0.5, details

        actual_lower = actual_output.lower()

        # 【优化点】使用模块级预编译正则提取双引号内的关键字
        expected_keywords = [kw.strip() for kw in _QUOTED_RE.findall(expected_output)]
        if not expected_keywords:
            expected_keywords = [expected_output.lower()[:30]]

        matched_keywords = [kw for kw in expected_keywords if kw.lower() in actual_lower]

        if matched_keywords:
            details["goal_achieved"] = True
            details["evidence"].append(f"匹配到关键词: {matched_keywords}")
            score = len(matched_keywords) / len(expected_keywords)
        else:
            similarity = SequenceMatcher(None, actual_output, expected_output).ratio()
            if similarity > 0.6:
                details["goal_achieved"] = True
                details["evidence"].append(f"内容相似度较高 ({similarity:.2f})")
                score = similarity
            else:
                score = 0.2

        if steps_data:
            action_types = {step.get("action", "") for step in steps_data}
            if "finish" in action_types or "summarize" in action_types:
                score = min(1.0, score + 0.1)

        return round(score, 4), details

    def _validate_reasoning_chain(self, request: EvaluationSchema) -> DomainResponse:
        """核心解算大脑：全量验证推理链合规性"""
        trajectory_id = self.get_payload_data(request, "trajectory_id")
        steps_data = self.get_payload_data(request, "steps", [])
        expected_intermediate = self.get_payload_data(request, "expected_intermediate", {})
        goal_description = self.get_payload_data(request, "goal_description", "")

        steps: list[TrajectoryStep] | None = None

        if trajectory_id:
            with self._trajectory_lock:
                if trajectory_id in self.trajectories:
                    steps = self.trajectories[trajectory_id].steps

        if steps is None:
            if steps_data:
                local_trajectory = AgentTrajectory(
                    trajectory_id=f"reasoning-{request.id}",
                    case_id=request.id,
                    model_name=self.get_payload_data(request, "model_name", "unknown"),
                )
                for i, step_data in enumerate(steps_data):
                    local_trajectory.add_step(
                        TrajectoryStep(
                            step_id=f"step-{i}",
                            action=step_data.get("action", "unknown"),
                            thought=step_data.get("thought"),
                            tool_name=step_data.get("tool_name"),
                            tool_args=step_data.get("tool_args"),
                            tool_result=step_data.get("tool_result"),
                            observation=step_data.get("observation"),
                            timestamp=step_data.get("timestamp", time.time()),
                        )
                    )
                steps = local_trajectory.steps
            else:
                return DomainResponse(
                    is_valid=False,
                    error="无法验证推理链：trajectory_id 对应的存储不存在且未提供 steps 列表",
                )

        chain_validity = self._check_reasoning_chain_validity(steps)
        logical_coherence = self._check_enhanced_coherence(steps, goal_description)
        intermediate_validation = self._validate_intermediate_results(steps, expected_intermediate)
        circular_detection = self._detect_circular_reasoning(steps)
        contradiction_detection = self._detect_contradictions(steps)

        overall_score = (
            chain_validity["score"] * 0.25
            + logical_coherence["score"] * 0.25
            + intermediate_validation["score"] * 0.25
            + (1.0 - circular_detection["circular_score"]) * 0.15
            + (1.0 - contradiction_detection["contradiction_score"]) * 0.10
        )

        return DomainResponse(
            is_valid=True,
            text="推理链全面验证完成",
            score=round(overall_score, 4),
            data={
                "trajectory_id": trajectory_id,
                "chain_validity": chain_validity,
                "logical_coherence": logical_coherence,
                "intermediate_validation": intermediate_validation,
                "circular_reasoning": circular_detection,
                "contradictions": contradiction_detection,
                "overall_score": round(overall_score, 4),
            },
        )

    def _check_reasoning_chain_validity(self, steps: list[TrajectoryStep]) -> dict[str, Any]:
        if len(steps) < 2:
            return {"score": 0.5, "message": "步骤数不足，无法验证推理链"}

        valid_transitions = 0
        transitions = []

        for i in range(len(steps) - 1):
            current = steps[i]
            next_step = steps[i + 1]

            is_valid = False
            match (current.action, next_step.action):
                case ("thought", "tool" | "thought" | "finish"):
                    is_valid = True
                    reason = "思考后执行有效动作"
                case ("tool", "thought" | "finish"):
                    is_valid = True
                    reason = "工具执行后进行思考或结束"
                case ("finish", _):
                    is_valid = True
                    reason = "已到达结束状态"
                case _:
                    reason = f"异常状态机转换: {current.action} -> {next_step.action}"

            transitions.append(
                {
                    "from_step": i,
                    "from_action": current.action,
                    "to_step": i + 1,
                    "to_action": next_step.action,
                    "valid": is_valid,
                    "reason": reason,
                }
            )

            if is_valid:
                valid_transitions += 1

        chain_score = valid_transitions / (len(steps) - 1)

        return {
            "score": round(chain_score, 4),
            "valid_transitions": valid_transitions,
            "total_transitions": len(steps) - 1,
            "transitions": transitions,
        }

    def _check_enhanced_coherence(
        self, steps: list[TrajectoryStep], goal_description: str = ""
    ) -> dict[str, Any]:
        if len(steps) < 2:
            return {"score": 0.5, "message": "步骤数不足，无法评估逻辑连贯性"}

        coherence_score = 0.0
        coherence_issues = []
        total_checks = 0

        for i in range(len(steps) - 1):
            current = steps[i]
            next_step = steps[i + 1]
            total_checks += 1

            if current.tool_result and next_step.thought:
                # 【优化点】改为调用全局预编译正则进行分词，避免局部高频编译
                tool_keywords = _WORD_RE.findall(str(current.tool_result).lower())[:10]
                thought_keywords = _WORD_RE.findall(str(next_step.thought).lower())[:10]

                if set(tool_keywords) & set(thought_keywords):
                    coherence_score += 1.0
                else:
                    coherence_issues.append(f"步骤{i}的工具结果未在步骤{i + 1}的思考中体现")

            if current.thought and next_step.thought:
                next_thought = str(next_step.thought).lower()
                if any(
                    kw in next_thought
                    for kw in ("因此", "所以", "于是", "then", "therefore", "thus")
                ):
                    coherence_score += 0.5
                elif any(kw in next_thought for kw in ("但是", "but", "however")):
                    coherence_score += 0.3

        if goal_description:
            goal_keywords = set(_WORD_RE.findall(goal_description.lower())[:15])
            for step in steps:
                thought_keywords = set(_WORD_RE.findall((step.thought or "").lower())[:10])
                if goal_keywords & thought_keywords:
                    coherence_score += 0.2
                    total_checks += 1

        avg_coherence = coherence_score / total_checks if total_checks > 0 else 0.0

        return {
            "score": round(min(1.0, avg_coherence), 4),
            "issues": coherence_issues,
            "total_checks": total_checks,
            "coherent_checks": int(coherence_score),
        }

    def _validate_intermediate_results(
        self, steps: list[TrajectoryStep], expected_intermediate: dict[str, Any]
    ) -> dict[str, Any]:
        if not expected_intermediate:
            return {"score": 0.5, "message": "无期望中间结果，无法验证"}

        validated_count = 0.0
        total_expected = len(expected_intermediate)
        validations = []

        for step in steps:
            if step.step_id in expected_intermediate:
                expected = expected_intermediate[step.step_id]
                actual = step.tool_result or step.observation or step.thought

                if actual:
                    actual_str = str(actual)
                    expected_str = str(expected)
                    similarity = SequenceMatcher(None, actual_str, expected_str).ratio()

                    if similarity > 0.7:
                        validations.append(
                            {
                                "step_id": step.step_id,
                                "expected": expected,
                                "actual": actual_str[:100],
                                "valid": True,
                                "similarity": round(similarity, 4),
                                "message": "中间结果与期望高度匹配",
                            }
                        )
                        validated_count += 1.0
                    elif similarity > 0.4:
                        validations.append(
                            {
                                "step_id": step.step_id,
                                "expected": expected,
                                "actual": actual_str[:100],
                                "valid": True,
                                "similarity": round(similarity, 4),
                                "message": "中间结果与期望部分匹配",
                            }
                        )
                        validated_count += 0.5
                    else:
                        validations.append(
                            {
                                "step_id": step.step_id,
                                "expected": expected,
                                "actual": actual_str[:100],
                                "valid": False,
                                "similarity": round(similarity, 4),
                                "message": "中间结果与期望差距较大",
                            }
                        )

        validation_score = validated_count / total_expected if total_expected > 0 else 0.0

        return {
            "score": round(validation_score, 4),
            "validated_count": validated_count,
            "total_expected": total_expected,
            "validations": validations,
        }

    def _detect_circular_reasoning(self, steps: list[TrajectoryStep]) -> dict[str, Any]:
        """检测循环论证（复读机特征）"""
        thought_history: list[str] = []
        circular_occurrences = []
        circular_score = 0.0

        for i, step in enumerate(steps):
            if step.thought:
                thought = str(step.thought).strip()

                for j, prev_thought in enumerate(thought_history):
                    similarity = SequenceMatcher(None, thought, prev_thought).ratio()
                    if similarity > 0.8 and i - j > 1:
                        circular_occurrences.append(
                            {
                                "step_current": i,
                                "step_previous": j,
                                "similarity": round(similarity, 4),
                                "current_thought": thought[:100],
                                "previous_thought": prev_thought[:100],
                            }
                        )
                        circular_score += similarity

                thought_history.append(thought)

        if thought_history:
            circular_score = circular_score / len(thought_history)

        return {
            "circular_score": round(min(1.0, circular_score), 4),
            "circular_occurrences": circular_occurrences,
            "total_thoughts": len(thought_history),
            "circular_detected": len(circular_occurrences) > 0,
        }

    def _detect_contradictions(self, steps: list[TrajectoryStep]) -> dict[str, Any]:
        """检测论点前后矛盾"""
        statements: list[tuple[int, str]] = []
        contradictions = []
        contradiction_score = 0.0
        negation_keywords = (
            "不是",
            "没有",
            "不应该",
            "错误",
            "否定",
            "相反",
            "但是",
            "然而",
            "but",
            "however",
            "not",
            "never",
            "no",
        )

        for i, step in enumerate(steps):
            if step.thought:
                statements.append((i, str(step.thought).strip()))

        for i, (step_i, stmt_i) in enumerate(statements):
            for step_j, stmt_j in statements[i + 1 :]:
                similarity = SequenceMatcher(None, stmt_i, stmt_j).ratio()

                if similarity < 0.3:
                    has_negation_i = any(kw in stmt_i for kw in negation_keywords)
                    has_negation_j = any(kw in stmt_j for kw in negation_keywords)

                    if has_negation_i and has_negation_j:
                        continue

                    if has_negation_i or has_negation_j:
                        contradictions.append(
                            {
                                "step_1": step_i,
                                "statement_1": stmt_i[:150],
                                "step_2": step_j,
                                "statement_2": stmt_j[:150],
                                "reason": "包含反向转折或否定词，上下文语句可能存在前后矛盾",
                            }
                        )
                        contradiction_score += 0.3

        if statements:
            contradiction_score = contradiction_score / len(statements)

        return {
            "contradiction_score": round(min(1.0, contradiction_score), 4),
            "contradictions": contradictions,
            "total_statements": len(statements),
            "contradiction_detected": len(contradictions) > 0,
        }

    def list_trajectories(self) -> list[str]:
        """线程安全地列出所有已存盘的轨迹 ID"""
        with self._trajectory_lock:
            return list(self.trajectories.keys())

    def clear_data(self) -> None:
        """安全清空轨迹存储器"""
        with self._trajectory_lock:
            self.trajectories.clear()
        logger.info("TrajectoryEvaluator 数据仓库已完全重置清空")
