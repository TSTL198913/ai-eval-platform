import json
import re
import time
from difflib import SequenceMatcher

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import AgentTrajectory, DomainResponse, EvaluationSchema, TrajectoryStep


@EvaluatorFactory.register("trajectory")
class TrajectoryEvaluator(BaseEvaluator):
    """Trajectory 轨迹评估器

    记录和评估 Agent 的决策路径，支持：
    - 轨迹记录
    - 轨迹回放
    - 路径分析
    - 决策质量评估
    """

    def __init__(self, client=None):
        super().__init__(client)
        self.trajectories = {}

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = self.get_payload_data(request, "action", "evaluate")
        trajectory_id = self.get_payload_data(request, "trajectory_id")

        if action == "record":
            return self._record_trajectory(request)
        elif action == "replay":
            return self._replay_trajectory(trajectory_id)
        elif action == "analyze":
            return self._analyze_trajectory(request)
        elif action == "validate_decision_path":
            return self._validate_decision_path(request)
        elif action == "reflect":
            return self._self_reflection(request)
        elif action == "three_tier_evaluate":
            return self._three_tier_evaluate(request)
        elif action == "validate_reasoning_chain":
            return self._validate_reasoning_chain(request)
        else:
            return self._evaluate_trajectory(request)

    def _record_trajectory(self, request: EvaluationSchema) -> DomainResponse:
        trajectory_id = self.get_payload_data(request, "trajectory_id")
        case_id = request.id
        model_name = self.get_payload_data(request, "model_name", "unknown")
        steps_data = self.get_payload_data(request, "steps", [])

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

        self.trajectories[trajectory_id] = trajectory

        return DomainResponse(
            is_valid=True,
            text=f"轨迹 {trajectory_id} 已记录",
            score=1.0,
            data={
                "trajectory_id": trajectory_id,
                "steps_count": len(trajectory.steps),
                "total_tokens": trajectory.total_tokens,
                "total_latency_ms": trajectory.total_latency_ms,
                "success": trajectory.success,
            },
        )

    def _replay_trajectory(self, trajectory_id: str) -> DomainResponse:
        if trajectory_id not in self.trajectories:
            return DomainResponse(
                is_valid=False,
                error=f"轨迹 {trajectory_id} 不存在",
            )

        trajectory = self.trajectories[trajectory_id]

        return DomainResponse(
            is_valid=True,
            text=f"轨迹 {trajectory_id} 回放",
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
        trajectory_id = self.get_payload_data(request, "trajectory_id")

        if trajectory_id not in self.trajectories:
            return DomainResponse(
                is_valid=False,
                error=f"轨迹 {trajectory_id} 不存在",
            )

        trajectory = self.trajectories[trajectory_id]

        analysis = self._perform_analysis(trajectory)

        return DomainResponse(
            is_valid=True,
            text=f"轨迹 {trajectory_id} 分析完成",
            score=analysis.get("overall_score", 0.5),
            data={
                "trajectory_id": trajectory_id,
                **analysis,
            },
        )

    def _evaluate_trajectory(self, request: EvaluationSchema) -> DomainResponse:
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
            from difflib import SequenceMatcher

            similarity = SequenceMatcher(None, actual_output, expected_output).ratio()
            analysis["output_similarity"] = similarity
            analysis["overall_score"] = (analysis.get("overall_score", 0.5) + similarity) / 2

        return DomainResponse(
            is_valid=True,
            text="轨迹评估完成",
            score=analysis.get("overall_score", 0.5),
            data=analysis,
        )

    def _perform_analysis(self, trajectory: AgentTrajectory) -> dict:
        steps = trajectory.steps

        tool_usage_count = sum(1 for step in steps if step.tool_name)
        total_thinking_time = sum(step.latency_ms for step in steps)
        avg_step_latency = total_thinking_time / len(steps) if steps else 0

        actions = [step.action for step in steps]
        action_variety = len(set(actions)) / len(actions) if actions else 0

        tool_success_rate = 0
        if tool_usage_count > 0:
            successful_tool_calls = sum(
                1 for step in steps if step.tool_name and step.tool_result
            )
            tool_success_rate = successful_tool_calls / tool_usage_count

        efficiency_score = min(1.0, max(0.0, 1.0 - (len(steps) - 5) * 0.1)) if len(steps) > 0 else 0.5

        overall_score = (
            efficiency_score * 0.3
            + tool_success_rate * 0.3
            + action_variety * 0.2
            + (1.0 if trajectory.success else 0.5) * 0.2
        )

        return {
            "steps_count": len(steps),
            "tool_usage_count": tool_usage_count,
            "tool_success_rate": tool_success_rate,
            "total_tokens": trajectory.total_tokens,
            "total_latency_ms": trajectory.total_latency_ms,
            "avg_step_latency_ms": avg_step_latency,
            "action_variety": action_variety,
            "efficiency_score": efficiency_score,
            "success": trajectory.success,
            "overall_score": overall_score,
        }

    def list_trajectories(self) -> list[str]:
        return list(self.trajectories.keys())

    def _validate_decision_path(self, request: EvaluationSchema) -> DomainResponse:
        trajectory_id = self.get_payload_data(request, "trajectory_id")
        expected_path = self.get_payload_data(request, "expected_path", [])
        steps_data = self.get_payload_data(request, "steps", [])

        if trajectory_id and trajectory_id in self.trajectories:
            trajectory = self.trajectories[trajectory_id]
            steps = trajectory.steps
        elif steps_data:
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
            steps = trajectory.steps
        else:
            return DomainResponse(
                is_valid=False,
                error="trajectory_id 或 steps 不能为空",
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
            score=overall_score,
            data={
                "trajectory_id": trajectory_id,
                "path_validity": path_validity,
                "logical_coherence": logical_coherence,
                "goal_relevance": goal_relevance,
                "actual_actions": actual_actions,
                "actual_tools": actual_tools,
                "expected_path": expected_path,
                "overall_score": overall_score,
            },
        )

    def _check_path_validity(self, steps: list[TrajectoryStep], expected_path: list) -> dict:
        if not expected_path:
            return {"score": 0.5, "message": "无期望路径，无法验证", "matches": []}

        actual_actions = [step.action for step in steps]
        matches = []

        for i, expected_action in enumerate(expected_path):
            if i < len(actual_actions):
                if actual_actions[i] == expected_action:
                    matches.append({"step": i, "expected": expected_action, "actual": actual_actions[i], "match": True})
                else:
                    matches.append({"step": i, "expected": expected_action, "actual": actual_actions[i], "match": False})

        correct_matches = sum(1 for m in matches if m["match"])
        score = correct_matches / len(expected_path) if expected_path else 0.0

        return {
            "score": score,
            "matches": matches,
            "correct_count": correct_matches,
            "total_expected": len(expected_path),
        }

    def _check_logical_coherence(self, steps: list[TrajectoryStep]) -> dict:
        if len(steps) < 2:
            return {"score": 0.5, "message": "步骤数不足，无法评估逻辑连贯性"}

        coherence_score = 0.0
        coherence_issues = []

        for i in range(len(steps) - 1):
            current_step = steps[i]
            next_step = steps[i + 1]

            if current_step.tool_result and next_step.thought:
                if current_step.tool_name in next_step.thought:
                    coherence_score += 1.0
                else:
                    coherence_issues.append(f"步骤{i}的工具结果未在步骤{i+1}的思考中体现")

        avg_coherence = coherence_score / (len(steps) - 1) if (len(steps) - 1) > 0 else 0.0

        return {
            "score": avg_coherence,
            "issues": coherence_issues,
            "checked_pairs": len(steps) - 1,
            "coherent_pairs": int(coherence_score),
        }

    def _check_goal_relevance(self, steps: list[TrajectoryStep]) -> dict:
        if not steps:
            return {"score": 0.0, "message": "无步骤可评估"}

        relevant_steps = 0
        irrelevant_steps = []

        for i, step in enumerate(steps):
            thought = step.thought or ""
            if any(keyword in thought.lower() for keyword in ["goal", "目标", "objective", "任务", "需要", "应该"]):
                relevant_steps += 1
            elif step.action in ["finish", "end", "summarize", "总结"]:
                relevant_steps += 1
            else:
                irrelevant_steps.append(f"步骤{i}: {step.action}")

        relevance_score = relevant_steps / len(steps)

        return {
            "score": relevance_score,
            "relevant_steps": relevant_steps,
            "total_steps": len(steps),
            "irrelevant_steps": irrelevant_steps,
        }

    def _self_reflection(self, request: EvaluationSchema) -> DomainResponse:
        trajectory_id = self.get_payload_data(request, "trajectory_id")
        steps_data = self.get_payload_data(request, "steps", [])
        actual_output = self.get_payload_data(request, "actual_output")
        expected_output = self.get_payload_data(request, "expected_output")

        if trajectory_id and trajectory_id in self.trajectories:
            trajectory = self.trajectories[trajectory_id]
        elif steps_data:
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
                is_valid=False,
                error="trajectory_id 或 steps 不能为空",
            )

        reflection = self._perform_reflection(trajectory, expected_output)

        return DomainResponse(
            is_valid=True,
            text="自我反思完成",
            score=reflection.get("reflection_score", 0.5),
            data=reflection,
        )

    def _perform_reflection(self, trajectory: AgentTrajectory, expected_output: str | None = None) -> dict:
        steps = trajectory.steps
        actual_output = trajectory.final_output

        reflection = {
            "steps_analyzed": len(steps),
            "reflection_score": 0.0,
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }

        if len(steps) == 0:
            reflection["reflection_score"] = 0.0
            reflection["weaknesses"].append("无执行步骤")
            return reflection

        reflection["strengths"].append(f"完成了{len(steps)}个执行步骤")

        for i, step in enumerate(steps):
            if step.thought:
                if len(step.thought) > 10:
                    reflection["strengths"].append(f"步骤{i}有详细的思考过程")
                else:
                    reflection["weaknesses"].append(f"步骤{i}思考过程过于简略")

            if step.tool_name and step.tool_result:
                reflection["strengths"].append(f"步骤{i}成功调用工具{step.tool_name}")

        if expected_output and actual_output:
            similarity = SequenceMatcher(None, actual_output, expected_output).ratio()
            reflection["output_similarity"] = similarity
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

        reflection["reflection_score"] = min(1.0, 0.5 + len(reflection["strengths"]) * 0.1 - len(reflection["weaknesses"]) * 0.05)

        return reflection

    def _three_tier_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        actual_output = self.get_payload_data(request, "actual_output")
        expected_output = self.get_payload_data(request, "expected_output")
        format_spec = self.get_payload_data(request, "format_spec", {})
        steps_data = self.get_payload_data(request, "steps", [])

        if not actual_output:
            return DomainResponse(is_valid=False, error="actual_output 不能为空")

        tier1_score, tier1_details = self._evaluate_l1_syntax(actual_output, format_spec)
        tier2_score, tier2_details = self._evaluate_l2_semantic(actual_output, expected_output)
        tier3_score, tier3_details = self._evaluate_l3_goal(actual_output, expected_output, steps_data)

        overall_score = tier1_score * 0.25 + tier2_score * 0.35 + tier3_score * 0.4

        return DomainResponse(
            is_valid=True,
            text="三层成功标准评估完成",
            score=overall_score,
            data={
                "tier1": {"name": "语法层", "score": tier1_score, **tier1_details},
                "tier2": {"name": "语义层", "score": tier2_score, **tier2_details},
                "tier3": {"name": "目标层", "score": tier3_score, **tier3_details},
                "overall_score": overall_score,
            },
        )

    def _evaluate_l1_syntax(self, actual_output: str, format_spec: dict) -> tuple[float, dict]:
        details = {
            "valid_format": True,
            "errors": [],
        }

        required_format = format_spec.get("type", "")
        if required_format == "json":
            try:
                json.loads(actual_output)
                details["valid_format"] = True
            except json.JSONDecodeError as e:
                details["valid_format"] = False
                details["errors"].append(f"JSON格式错误: {str(e)}")
                return 0.0, details
        elif required_format == "markdown":
            if not any(m in actual_output for m in ["#", "*", "**", "- "]):
                details["valid_format"] = False
                details["errors"].append("缺少Markdown格式标记")

        if not actual_output.strip():
            details["valid_format"] = False
            details["errors"].append("输出为空")
            return 0.0, details

        return 1.0, details

    def _evaluate_l2_semantic(self, actual_output: str, expected_output: str | None = None) -> tuple[float, dict]:
        details = {
            "relevant": True,
            "similarity": 0.0,
        }

        if not expected_output:
            return 0.5, details

        similarity = SequenceMatcher(None, actual_output, expected_output).ratio()
        details["similarity"] = similarity

        if similarity > 0.7:
            details["relevant"] = True
            score = min(1.0, similarity)
        elif similarity > 0.3:
            details["relevant"] = True
            score = 0.5 + similarity * 0.5
        else:
            details["relevant"] = False
            score = 0.2

        return score, details

    def _evaluate_l3_goal(self, actual_output: str, expected_output: str | None = None, steps_data: list = None) -> tuple[float, dict]:
        if steps_data is None:
            steps_data = []
        details = {
            "goal_achieved": False,
            "evidence": [],
        }

        if not expected_output:
            return 0.5, details

        expected_lower = expected_output.lower()
        actual_lower = actual_output.lower()

        expected_keywords = [kw.strip() for kw in re.findall(r'"([^"]*)"', expected_output)]
        if not expected_keywords:
            expected_keywords = [expected_lower[:30]]

        matched_keywords = []
        for keyword in expected_keywords:
            if keyword.lower() in actual_lower:
                matched_keywords.append(keyword)

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

        return score, details

    def _validate_reasoning_chain(self, request: EvaluationSchema) -> DomainResponse:
        trajectory_id = self.get_payload_data(request, "trajectory_id")
        steps_data = self.get_payload_data(request, "steps", [])
        expected_intermediate = self.get_payload_data(request, "expected_intermediate", {})
        goal_description = self.get_payload_data(request, "goal_description", "")

        if trajectory_id and trajectory_id in self.trajectories:
            trajectory = self.trajectories[trajectory_id]
            steps = trajectory.steps
        elif steps_data:
            trajectory = AgentTrajectory(
                trajectory_id=f"reasoning-{request.id}",
                case_id=request.id,
                model_name=self.get_payload_data(request, "model_name", "unknown"),
            )
            for i, step_data in enumerate(steps_data):
                step = TrajectoryStep(
                    step_id=f"step-{i}",
                    action=step_data.get("action", "unknown"),
                    thought=step_data.get("thought"),
                    tool_name=step_data.get("tool_name"),
                    tool_args=step_data.get("tool_args"),
                    tool_result=step_data.get("tool_result"),
                    observation=step_data.get("observation"),
                    timestamp=step_data.get("timestamp", time.time()),
                )
                trajectory.add_step(step)
            steps = trajectory.steps
        else:
            return DomainResponse(
                is_valid=False,
                error="trajectory_id 或 steps 不能为空",
            )

        chain_validity = self._check_reasoning_chain_validity(steps, expected_intermediate)
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
            text="推理链验证完成",
            score=overall_score,
            data={
                "trajectory_id": trajectory_id,
                "chain_validity": chain_validity,
                "logical_coherence": logical_coherence,
                "intermediate_validation": intermediate_validation,
                "circular_reasoning": circular_detection,
                "contradictions": contradiction_detection,
                "overall_score": overall_score,
            },
        )

    def _check_reasoning_chain_validity(self, steps: list[TrajectoryStep], expected_intermediate: dict) -> dict:
        if len(steps) < 2:
            return {"score": 0.5, "message": "步骤数不足，无法验证推理链"}

        valid_transitions = 0
        transitions = []

        for i in range(len(steps) - 1):
            current = steps[i]
            next_step = steps[i + 1]

            is_valid = False
            reason = ""

            if current.action == "thought" and next_step.action in ["tool", "thought", "finish"]:
                is_valid = True
                reason = "思考后执行有效动作"
            elif current.action == "tool" and next_step.action in ["thought", "finish"]:
                is_valid = True
                reason = "工具执行后进行思考或结束"
            elif current.action == "finish":
                is_valid = True
                reason = "已到达结束状态"
            else:
                reason = f"异常转换: {current.action} -> {next_step.action}"

            transitions.append({
                "from_step": i,
                "from_action": current.action,
                "to_step": i + 1,
                "to_action": next_step.action,
                "valid": is_valid,
                "reason": reason,
            })

            if is_valid:
                valid_transitions += 1

        chain_score = valid_transitions / (len(steps) - 1)

        return {
            "score": chain_score,
            "valid_transitions": valid_transitions,
            "total_transitions": len(steps) - 1,
            "transitions": transitions,
        }

    def _check_enhanced_coherence(self, steps: list[TrajectoryStep], goal_description: str = "") -> dict:
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
                tool_result_str = str(current.tool_result)[:200]
                thought_str = str(next_step.thought)[:200]

                tool_keywords = re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{2,}\b', tool_result_str.lower())[:10]
                thought_keywords = re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{2,}\b', thought_str.lower())[:10]

                common_keywords = set(tool_keywords) & set(thought_keywords)
                if common_keywords:
                    coherence_score += 1.0
                else:
                    coherence_issues.append(f"步骤{i}的工具结果未在步骤{i+1}的思考中体现")

            if current.thought and next_step.thought:
                str(current.thought).lower()
                next_thought = str(next_step.thought).lower()

                if any(kw in next_thought for kw in ["因此", "所以", "于是", "then", "therefore", "thus"]):
                    coherence_score += 0.5
                elif "但是" in next_thought or "but" in next_thought or "however" in next_thought:
                    coherence_score += 0.3

        if goal_description:
            goal_keywords = set(re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{2,}\b', goal_description.lower())[:15])
            for step in steps:
                thought_keywords = set(re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{2,}\b', (step.thought or "").lower())[:10])
                if goal_keywords & thought_keywords:
                    coherence_score += 0.2
                    total_checks += 1

        avg_coherence = coherence_score / total_checks if total_checks > 0 else 0.0

        return {
            "score": min(1.0, avg_coherence),
            "issues": coherence_issues,
            "total_checks": total_checks,
            "coherent_checks": int(coherence_score),
        }

    def _validate_intermediate_results(self, steps: list[TrajectoryStep], expected_intermediate: dict) -> dict:
        if not expected_intermediate:
            return {"score": 0.5, "message": "无期望中间结果，无法验证"}

        validated_count = 0
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
                        validations.append({
                            "step_id": step.step_id,
                            "expected": expected,
                            "actual": actual_str[:100] if len(actual_str) > 100 else actual_str,
                            "valid": True,
                            "similarity": similarity,
                            "message": "中间结果与期望高度匹配",
                        })
                        validated_count += 1
                    elif similarity > 0.4:
                        validations.append({
                            "step_id": step.step_id,
                            "expected": expected,
                            "actual": actual_str[:100] if len(actual_str) > 100 else actual_str,
                            "valid": True,
                            "similarity": similarity,
                            "message": "中间结果与期望部分匹配",
                        })
                        validated_count += 0.5
                    else:
                        validations.append({
                            "step_id": step.step_id,
                            "expected": expected,
                            "actual": actual_str[:100] if len(actual_str) > 100 else actual_str,
                            "valid": False,
                            "similarity": similarity,
                            "message": "中间结果与期望差距较大",
                        })

        validation_score = validated_count / total_expected if total_expected > 0 else 0.0

        return {
            "score": validation_score,
            "validated_count": validated_count,
            "total_expected": total_expected,
            "validations": validations,
        }

    def _detect_circular_reasoning(self, steps: list[TrajectoryStep]) -> dict:
        thought_history = []
        circular_occurrences = []
        circular_score = 0.0

        for i, step in enumerate(steps):
            if step.thought:
                thought = str(step.thought).strip()

                for j, prev_thought in enumerate(thought_history):
                    similarity = SequenceMatcher(None, thought, prev_thought).ratio()

                    if similarity > 0.8 and i - j > 1:
                        circular_occurrences.append({
                            "step_current": i,
                            "step_previous": j,
                            "similarity": similarity,
                            "current_thought": thought[:100],
                            "previous_thought": prev_thought[:100],
                        })
                        circular_score += similarity

                thought_history.append(thought)

        if thought_history:
            circular_score = circular_score / len(thought_history)

        return {
            "circular_score": min(1.0, circular_score),
            "circular_occurrences": circular_occurrences,
            "total_thoughts": len(thought_history),
            "circular_detected": len(circular_occurrences) > 0,
        }

    def _detect_contradictions(self, steps: list[TrajectoryStep]) -> dict:
        statements = []
        contradictions = []
        contradiction_score = 0.0

        for i, step in enumerate(steps):
            if step.thought:
                statements.append((i, str(step.thought).strip()))

        for i, (step_i, stmt_i) in enumerate(statements):
            for _j, (step_j, stmt_j) in enumerate(statements[i + 1:], i + 1):
                similarity = SequenceMatcher(None, stmt_i, stmt_j).ratio()

                if similarity < 0.3:
                    negation_keywords = ["不是", "没有", "不应该", "错误", "否定", "相反", "但是", "然而", "but", "however", "not", "never", "no"]

                    has_negation_i = any(kw in stmt_i for kw in negation_keywords)
                    has_negation_j = any(kw in stmt_j for kw in negation_keywords)

                    if has_negation_i and has_negation_j:
                        continue

                    if has_negation_i or has_negation_j:
                        contradictions.append({
                            "step_1": step_i,
                            "statement_1": stmt_i[:150],
                            "step_2": step_j,
                            "statement_2": stmt_j[:150],
                            "reason": "包含否定关键词的语句可能存在矛盾",
                        })
                        contradiction_score += 0.3

        if statements:
            contradiction_score = contradiction_score / len(statements)

        return {
            "contradiction_score": min(1.0, contradiction_score),
            "contradictions": contradictions,
            "total_statements": len(statements),
            "contradiction_detected": len(contradictions) > 0,
        }
