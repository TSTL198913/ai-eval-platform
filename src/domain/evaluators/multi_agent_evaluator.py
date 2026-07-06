"""多Agent协作评估器

用于评估多Agent系统中的协作效率和质量，包括：
- Agent间通信质量评估
- 任务分配效率评估
- 协作完成率评估
- 冲突检测评估

遵循单一职责原则，状态管理由 MultiAgentStateManager 负责。
"""

import concurrent.futures
import logging
import time
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.multi_agent_state_manager import AgentInfo
from src.domain.evaluators.multi_agent_state_manager import AgentMessage
from src.domain.evaluators.multi_agent_state_manager import AgentTask
from src.domain.evaluators.multi_agent_state_manager import Conflict
from src.domain.evaluators.multi_agent_state_manager import ConflictType
from src.domain.evaluators.multi_agent_state_manager import MessageType
from src.domain.evaluators.multi_agent_state_manager import MultiAgentStateManager
from src.domain.evaluators.multi_agent_state_manager import TaskStatus
from src.domain.evaluators.multi_agent_state_manager import sanitize_input
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("multi_agent")
class MultiAgentEvaluator(BaseEvaluator):
    """多Agent协作评估器"""

    def __init__(self, client=None):
        super().__init__(client)
        self._state_manager = MultiAgentStateManager()
        self.collaboration_sessions = {}

    async def _do_evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        import asyncio
        action = self.get_payload_data(request, "action", "evaluate")
        timeout_seconds = self.get_payload_data(request, "timeout", 30)
        logger.debug(f"MultiAgentEvaluator 异步执行动作: {action}, 超时时间: {timeout_seconds}秒")

        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = loop.run_in_executor(executor, self._execute_action, action, request)
                try:
                    return await asyncio.wait_for(future, timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    logger.error(f"MultiAgentEvaluator 异步执行动作 '{action}' 超时（{timeout_seconds}秒）")
                    return self.create_error_response(
                        error_message=f"评估器异步执行超时，已超过 {timeout_seconds} 秒",
                        error_code="EVALUATION_TIMEOUT",
                    )
        except Exception as e:
            logger.error(f"MultiAgentEvaluator 异步执行动作 '{action}' 失败: {e}")
            return self.create_error_response(
                error_message=f"评估器异步执行失败: {str(e)}",
                error_code="EVALUATION_ERROR",
            )

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = self.get_payload_data(request, "action", "evaluate")
        timeout_seconds = self.get_payload_data(request, "timeout", 30)
        logger.debug(f"MultiAgentEvaluator 正在执行动作: {action}, 超时时间: {timeout_seconds}秒")

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._execute_action, action, request)
                try:
                    return future.result(timeout=timeout_seconds)
                except concurrent.futures.TimeoutError:
                    logger.error(f"MultiAgentEvaluator 执行动作 '{action}' 超时（{timeout_seconds}秒）")
                    return self.create_error_response(
                        error_message=f"评估器执行超时，已超过 {timeout_seconds} 秒",
                        error_code="EVALUATION_TIMEOUT",
                    )
        except Exception as e:
            logger.error(f"MultiAgentEvaluator 执行动作 '{action}' 失败: {e}")
            return self.create_error_response(
                error_message=f"评估器执行失败: {str(e)}",
                error_code="EVALUATION_ERROR",
            )

    def _execute_action(self, action: str, request: EvaluationSchema) -> DomainResponse:
        match action:
            case "register_agent":
                return self._register_agent(request)
            case "record_message":
                return self._record_message(request)
            case "assign_task":
                return self._assign_task(request)
            case "update_task":
                return self._update_task(request)
            case "record_conflict":
                return self._record_conflict(request)
            case "resolve_conflict":
                return self._resolve_conflict(request)
            case "start_session":
                return self._start_collaboration_session(request)
            case "end_session":
                return self._end_collaboration_session(request)
            case "analyze":
                return self._analyze_collaboration(request)
            case _:
                return self._evaluate_collaboration(request)

    def _register_agent(self, request: EvaluationSchema) -> DomainResponse:
        agent_id = self.get_payload_data(request, "agent_id")
        role = self.get_payload_data(request, "role", "worker")
        capabilities = self.get_payload_data(request, "capabilities", [])

        if not agent_id:
            return self.create_error_response(error_message="agent_id 不能为空")

        success = self._state_manager.register_agent(agent_id, role, capabilities)
        if success:
            return self.create_success_response(
                text=f"Agent {agent_id} 注册成功",
                score=1.0,
                data={"agent_id": agent_id, "role": role, "capabilities": capabilities},
            )
        return self.create_error_response(error_message="Agent 注册失败")

    def _record_message(self, request: EvaluationSchema) -> DomainResponse:
        message_id = self.get_payload_data(request, "message_id")
        sender_id = self.get_payload_data(request, "sender_id")
        receiver_id = self.get_payload_data(request, "receiver_id")
        message_type = self.get_payload_data(request, "message_type", "request")
        content = self.get_payload_data(request, "content", "")
        latency_ms = self.get_payload_data(request, "latency_ms", 0.0)
        is_delivered = self.get_payload_data(request, "is_delivered", True)
        is_acknowledged = self.get_payload_data(request, "is_acknowledged", False)
        metadata = self.get_payload_data(request, "metadata", {})

        if not sender_id or not receiver_id:
            return self.create_error_response(error_message="sender_id 和 receiver_id 不能为空")

        try:
            from src.domain.evaluators.multi_agent_state_manager import MessageType
            MessageType(message_type)
        except ValueError:
            return self.create_error_response(error_message=f"无效的message_type: {message_type}")

        msg_id = self._state_manager.record_message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type,
            message_id=message_id,
            latency_ms=latency_ms,
            is_delivered=is_delivered,
            is_acknowledged=is_acknowledged,
            metadata=metadata,
        )

        if msg_id:
            return self.create_success_response(
                text="消息记录成功",
                score=1.0,
                data={
                    "message_id": msg_id,
                    "sender_id": sender_id,
                    "receiver_id": receiver_id,
                    "message_type": message_type,
                },
            )
        return self.create_error_response(error_message="消息记录失败")

    def _assign_task(self, request: EvaluationSchema) -> DomainResponse:
        task_id = self.get_payload_data(request, "task_id")
        agent_id = self.get_payload_data(request, "agent_id")
        description = self.get_payload_data(request, "description", "")
        priority = self.get_payload_data(request, "priority", 1)
        dependencies = self.get_payload_data(request, "dependencies", [])

        if not task_id or not agent_id:
            return self.create_error_response(error_message="task_id 和 agent_id 不能为空")

        if not self._state_manager.get_agent_info(agent_id):
            return self.create_error_response(error_message=f"Agent {agent_id} 未注册")

        success = self._state_manager.assign_task(
            task_id=task_id,
            agent_id=agent_id,
            description=description,
            priority=priority,
            dependencies=dependencies,
        )

        if success:
            return self.create_success_response(
                text=f"任务 {task_id} 已分配给 Agent {agent_id}",
                score=1.0,
                data={"task_id": task_id, "agent_id": agent_id, "status": "assigned"},
            )
        return self.create_error_response(error_message="任务分配失败")

    def _update_task(self, request: EvaluationSchema) -> DomainResponse:
        task_id = self.get_payload_data(request, "task_id")
        status = self.get_payload_data(request, "status")
        result = self.get_payload_data(request, "result")
        error = self.get_payload_data(request, "error", "")

        try:
            from src.domain.evaluators.multi_agent_state_manager import TaskStatus
            TaskStatus(status)
        except ValueError:
            return self.create_error_response(error_message=f"无效的status: {status}")

        if not self._state_manager.get_task_info(task_id):
            return self.create_error_response(error_message=f"任务 {task_id} 不存在")

        success = self._state_manager.update_task(
            task_id=task_id,
            status=status,
            result=result,
            error=error,
        )

        if success:
            return self.create_success_response(
                text=f"任务 {task_id} 状态已更新为 {status}",
                score=1.0,
                data={"task_id": task_id, "new_status": status},
            )
        return self.create_error_response(error_message="任务更新失败")

    def _record_conflict(self, request: EvaluationSchema) -> DomainResponse:
        conflict_id = self.get_payload_data(request, "conflict_id")
        conflict_type = self.get_payload_data(request, "conflict_type")
        agent_ids = self.get_payload_data(request, "agent_ids", [])
        description = self.get_payload_data(request, "description", "")

        if not agent_ids:
            return self.create_error_response(error_message="agent_ids 不能为空")

        try:
            from src.domain.evaluators.multi_agent_state_manager import ConflictType
            ConflictType(conflict_type)
        except ValueError:
            return self.create_error_response(error_message=f"无效的conflict_type: {conflict_type}")

        c_id = self._state_manager.record_conflict(
            conflict_type=conflict_type,
            agent_ids=agent_ids,
            description=description,
            conflict_id=conflict_id,
        )

        if c_id:
            return self.create_success_response(
                text="冲突已记录",
                score=1.0,
                data={
                    "conflict_id": c_id,
                    "conflict_type": conflict_type,
                    "agent_ids": agent_ids,
                },
            )
        return self.create_error_response(error_message="冲突记录失败")

    def _resolve_conflict(self, request: EvaluationSchema) -> DomainResponse:
        conflict_id = self.get_payload_data(request, "conflict_id")
        resolution = self.get_payload_data(request, "resolution", "")

        if not self._state_manager.get_conflict_info(conflict_id):
            return self.create_error_response(error_message=f"冲突 {conflict_id} 不存在")

        success = self._state_manager.resolve_conflict(
            conflict_id=conflict_id,
            resolution=resolution,
        )

        if success:
            return self.create_success_response(
                text=f"冲突 {conflict_id} 已解决",
                score=1.0,
                data={"conflict_id": conflict_id, "resolution": resolution},
            )
        return self.create_error_response(error_message="冲突解决失败")

    def _start_collaboration_session(self, request: EvaluationSchema) -> DomainResponse:
        session_id = self.get_payload_data(request, "session_id")
        agent_ids = self.get_payload_data(request, "agent_ids", [])
        goal = self.get_payload_data(request, "goal", "")

        if not session_id:
            return self.create_error_response(error_message="session_id 不能为空")

        success = self._state_manager.start_session(session_id, agent_ids, goal)
        if success:
            self.collaboration_sessions[session_id] = {
                "session_id": session_id,
                "agent_ids": agent_ids,
                "goal": goal,
                "status": "active",
            }
            return self.create_success_response(
                text=f"协作会话 {session_id} 已开始",
                score=1.0,
                data={"session_id": session_id, "agent_ids": agent_ids, "goal": goal},
            )
        return self.create_error_response(error_message="会话开始失败")

    def _end_collaboration_session(self, request: EvaluationSchema) -> DomainResponse:
        session_id = self.get_payload_data(request, "session_id")
        status = self.get_payload_data(request, "status", "completed")

        if session_id not in self.collaboration_sessions:
            return self.create_error_response(error_message=f"会话 {session_id} 不存在")

        duration = self._state_manager.end_session(session_id, status)
        if duration is None and session_id in self.collaboration_sessions:
            session_data = self.collaboration_sessions[session_id]
            if "end_time" in session_data and "start_time" in session_data:
                if session_data["end_time"] is not None:
                    duration = session_data["end_time"] - session_data["start_time"]
                else:
                    duration = time.time() - session_data["start_time"]
            elif "start_time" in session_data:
                duration = time.time() - session_data["start_time"]
        if duration is None:
            duration = 0.0
        if session_id in self.collaboration_sessions:
            self.collaboration_sessions[session_id]["status"] = status
        return self.create_success_response(
            text=f"协作会话 {session_id} 已结束",
            score=1.0,
            data={"session_id": session_id, "status": status, "duration_seconds": duration},
        )

    def _analyze_collaboration(self, request: EvaluationSchema) -> DomainResponse:
        session_id = self.get_payload_data(request, "session_id")
        analysis = self._analyze_session(session_id) if session_id else self._analyze_overall()

        return self.create_success_response(
            text="协作分析完成",
            score=analysis.get("overall_score", 0.5),
            data=analysis,
        )

    def _evaluate_collaboration(self, request: EvaluationSchema) -> DomainResponse:
        agents_data = self.get_payload_data(request, "agents", [])
        messages_data = self.get_payload_data(request, "messages", [])
        tasks_data = self.get_payload_data(request, "tasks", [])
        conflicts_data = self.get_payload_data(request, "conflicts", [])

        if not agents_data and not messages_data and not tasks_data:
            actual_output = self.get_payload_data(request, "actual_output", "")
            expected_output = self.get_payload_data(request, "expected_output", "")
            
            import difflib
            similarity = difflib.SequenceMatcher(None, actual_output, expected_output).ratio()
            
            return self.create_partial_response(
                text="多Agent协作评估（降级模式），基于输出相似度评估",
                score=similarity,
                dimensions_evaluated=["output_similarity"],
                dimensions_skipped=["communication", "task_efficiency", "conflict_resolution"],
                skip_reasons={
                    "communication": "缺少多Agent通信数据",
                    "task_efficiency": "缺少多Agent任务数据",
                    "conflict_resolution": "缺少多Agent冲突数据",
                },
                confidence=0.5,
                data={
                    "overall_score": similarity,
                    "output_similarity": similarity,
                    "mode": "fallback",
                },
            )

        parsed_agents, parsed_messages, parsed_tasks, parsed_conflicts = (
            self._parse_collaboration_data(agents_data, messages_data, tasks_data, conflicts_data)
        )

        analysis = self._analyze_overall(
            agents_map=parsed_agents,
            messages_list=parsed_messages,
            tasks_list=parsed_tasks,
            conflicts_list=parsed_conflicts,
        )

        return self.create_success_response(
            text="多Agent协作沙盒评估完成",
            score=analysis.get("overall_score", 0.5),
            data=analysis,
        )

    def _parse_collaboration_data(
        self,
        agents_data: list[dict],
        messages_data: list[dict],
        tasks_data: list[dict],
        conflicts_data: list[dict],
    ) -> tuple[dict[str, AgentInfo], list[AgentMessage], list[AgentTask], list[Conflict]]:
        parsed_agents: dict[str, AgentInfo] = {}
        for a in agents_data:
            aid = a.get("agent_id")
            if aid:
                parsed_agents[aid] = AgentInfo(
                    agent_id=aid,
                    role=a.get("role", "worker"),
                    capabilities=a.get("capabilities", []),
                    status=a.get("status", "active"),
                    message_count=a.get("message_count", 0),
                    completed_tasks=a.get("completed_tasks", 0),
                    failed_tasks=a.get("failed_tasks", 0),
                )

        parsed_messages = [
            AgentMessage(
                message_id=m.get("message_id", f"msg-{i}"),
                sender_id=m.get("sender_id", ""),
                receiver_id=m.get("receiver_id", ""),
                message_type=MessageType(m.get("message_type", "request")),
                content=m.get("content", ""),
                timestamp=m.get("timestamp", time.time()),
                latency_ms=m.get("latency_ms", 0.0),
                is_delivered=m.get("is_delivered", True),
                is_acknowledged=m.get("is_acknowledged", False),
            )
            for i, m in enumerate(messages_data)
        ]

        parsed_tasks = [
            AgentTask(
                task_id=t.get("task_id", ""),
                agent_id=t.get("agent_id", ""),
                description=t.get("description", ""),
                status=TaskStatus(t.get("status", "pending")),
                priority=t.get("priority", 1),
                assigned_at=t.get("assigned_at", 0.0),
                completed_at=t.get("completed_at", 0.0),
                dependencies=t.get("dependencies", []),
                result=t.get("result"),
                error=t.get("error"),
            )
            for t in tasks_data
        ]

        parsed_conflicts = [
            Conflict(
                conflict_id=c.get("conflict_id", f"conflict-{i}"),
                conflict_type=ConflictType(c.get("conflict_type", "task")),
                agent_ids=c.get("agent_ids", []),
                description=c.get("description", ""),
                timestamp=c.get("timestamp", time.time()),
                resolved=c.get("resolved", False),
                resolution=c.get("resolution"),
            )
            for i, c in enumerate(conflicts_data)
        ]

        return parsed_agents, parsed_messages, parsed_tasks, parsed_conflicts

    def _analyze_communication(self, messages: list[AgentMessage]) -> dict[str, Any]:
        if not messages:
            return {
                "total_messages": 0,
                "delivery_rate": 0.0,
                "acknowledgment_rate": 0.0,
                "avg_latency_ms": 0.0,
                "message_type_distribution": {},
                "communication_score": 0.5,
            }

        total_messages = len(messages)
        delivered_messages = sum(1 for m in messages if m.is_delivered)
        acknowledged_messages = sum(1 for m in messages if m.is_acknowledged)

        delivery_rate = delivered_messages / total_messages
        acknowledgment_rate = acknowledged_messages / total_messages

        latencies = [m.latency_ms for m in messages if m.latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        type_distribution: dict[str, int] = {}
        for msg in messages:
            msg_type = msg.message_type.value
            type_distribution[msg_type] = type_distribution.get(msg_type, 0) + 1

        latency_score = max(0.0, min(1.0, 1.0 - (avg_latency / 1000.0))) if avg_latency > 0 else 1.0
        communication_score = delivery_rate * 0.4 + acknowledgment_rate * 0.3 + latency_score * 0.3

        return {
            "total_messages": total_messages,
            "delivered_messages": delivered_messages,
            "acknowledged_messages": acknowledged_messages,
            "delivery_rate": round(delivery_rate, 4),
            "acknowledgment_rate": round(acknowledgment_rate, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "message_type_distribution": type_distribution,
            "communication_score": round(communication_score, 4),
        }

    def _analyze_tasks(self, tasks: list[AgentTask]) -> dict[str, Any]:
        if not tasks:
            return {
                "total_tasks": 0,
                "completion_rate": 0.0,
                "failure_rate": 0.0,
                "avg_completion_time_ms": 0.0,
                "task_efficiency_score": 0.5,
                "agent_task_distribution": {},
            }

        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed_tasks = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        pending_tasks = sum(1 for t in tasks if t.status == TaskStatus.PENDING)

        completion_rate = completed_tasks / total_tasks if total_tasks > 0 else 0.0
        failure_rate = failed_tasks / total_tasks if total_tasks > 0 else 0.0

        completion_times = [
            t.completed_at - t.assigned_at for t in tasks if t.completed_at > 0 and t.assigned_at > 0
        ]
        avg_completion_time_ms = (
            sum(completion_times) / len(completion_times) * 1000 if completion_times else 0.0
        )

        efficiency_score = completion_rate * 0.6 + (1.0 - failure_rate) * 0.4

        agent_task_distribution: dict[str, int] = {}
        for task in tasks:
            aid = task.agent_id
            agent_task_distribution[aid] = agent_task_distribution.get(aid, 0) + 1

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "pending_tasks": pending_tasks,
            "completion_rate": round(completion_rate, 4),
            "failure_rate": round(failure_rate, 4),
            "avg_completion_time_ms": round(avg_completion_time_ms, 2),
            "task_efficiency_score": round(efficiency_score, 4),
            "agent_task_distribution": agent_task_distribution,
        }

    def _analyze_conflicts(self, conflicts: list[Conflict] | None = None) -> dict[str, Any]:
        if conflicts is None:
            _, _, _, conflicts = self._state_manager.get_snapshot()
        return self._analyze_conflicts_for_agents(conflicts, None)

    def _analyze_conflicts_for_agents(
        self, conflicts: list[Conflict] | None, agent_ids: list[str] | None
    ) -> dict[str, Any]:
        if conflicts is None:
            _, _, _, conflicts = self._state_manager.get_snapshot()

        filtered_conflicts = (
            [c for c in conflicts if any(aid in c.agent_ids for aid in agent_ids)]
            if agent_ids
            else conflicts
        )

        if not filtered_conflicts:
            return {
                "total_conflicts": 0,
                "resolved_conflicts": 0,
                "unresolved_conflicts": 0,
                "resolution_rate": 0.0,
                "conflict_type_distribution": {},
                "conflict_resolution_score": 1.0,
            }

        total_conflicts = len(filtered_conflicts)
        resolved_conflicts = sum(1 for c in filtered_conflicts if c.resolved)
        unresolved_conflicts = total_conflicts - resolved_conflicts
        resolution_rate = resolved_conflicts / total_conflicts

        type_distribution: dict[str, int] = {}
        for conflict in filtered_conflicts:
            c_type = conflict.conflict_type.value
            type_distribution[c_type] = type_distribution.get(c_type, 0) + 1

        SEVERITY_WEIGHTS = {
            "resource": 1.0,
            "task": 0.8,
            "priority": 0.6,
            "communication": 0.4,
            "data": 0.5,
        }
        weighted_severity = sum(
            SEVERITY_WEIGHTS.get(c.conflict_type.value, 0.5)
            for c in filtered_conflicts
        ) / max(total_conflicts, 1)
        conflict_penalty = min(0.5, total_conflicts * weighted_severity / 20.0)
        conflict_resolution_score = resolution_rate * (1.0 - conflict_penalty)

        return {
            "total_conflicts": total_conflicts,
            "resolved_conflicts": resolved_conflicts,
            "unresolved_conflicts": unresolved_conflicts,
            "resolution_rate": round(resolution_rate, 4),
            "conflict_type_distribution": type_distribution,
            "conflict_resolution_score": round(max(0.0, conflict_resolution_score), 4),
        }

    def _analyze_collaboration_quality(
        self,
        agents_map: dict[str, AgentInfo] | None = None,
        tasks_len: int | None = None,
        messages_len: int | None = None,
    ) -> dict[str, Any]:
        if agents_map is None:
            agents_map, _, _, _ = self._state_manager.get_snapshot()
        if tasks_len is None:
            _, _, tasks_list, _ = self._state_manager.get_snapshot()
            tasks_len = len(tasks_list)
        if messages_len is None:
            _, messages_list, _, _ = self._state_manager.get_snapshot()
            messages_len = len(messages_list)

        if not agents_map:
            return {
                "active_agents": 0,
                "avg_messages_per_agent": 0.0,
                "avg_tasks_per_agent": 0.0,
                "agent_utilization_rate": 0.0,
                "collaboration_score": 0.5,
            }

        active_agents = len(agents_map)
        total_messages = messages_len
        total_tasks = tasks_len

        avg_messages_per_agent = total_messages / active_agents if active_agents > 0 else 0.0
        avg_tasks_per_agent = total_tasks / active_agents if active_agents > 0 else 0.0

        agents_with_tasks = sum(
            1 for a in agents_map.values() if a.completed_tasks > 0 or len(a.current_tasks) > 0
        )
        agent_utilization_rate = agents_with_tasks / active_agents

        if total_messages > 0 and total_tasks > 0:
            msg_task_ratio = total_messages / total_tasks
            if msg_task_ratio < 1:
                ratio_score = msg_task_ratio
            elif msg_task_ratio <= 5:
                ratio_score = 1.0
            else:
                ratio_score = max(0.5, 1.0 - (msg_task_ratio - 5) * 0.1)
            collaboration_score = ratio_score * 0.5 + agent_utilization_rate * 0.5
        else:
            collaboration_score = agent_utilization_rate if agents_map else 0.5

        task_counts = [a.completed_tasks + len(a.current_tasks) for a in agents_map.values()]
        if task_counts:
            avg_task_count = sum(task_counts) / len(task_counts)
            variance = sum((tc - avg_task_count) ** 2 for tc in task_counts) / len(task_counts)
            std_dev = variance ** 0.5
            balance_ratio = 1.0 - (std_dev / max(avg_task_count, 1))
            balance_ratio = max(0.0, min(1.0, balance_ratio))
        else:
            balance_ratio = 1.0

        resource_utilization = sum(
            len(a.current_tasks) + a.completed_tasks for a in agents_map.values()
        ) / max(active_agents * 10, 1)
        resource_utilization = min(1.0, resource_utilization)

        return {
            "active_agents": active_agents,
            "total_agents": active_agents,
            "avg_messages_per_agent": round(avg_messages_per_agent, 2),
            "avg_tasks_per_agent": round(avg_tasks_per_agent, 2),
            "agent_utilization_rate": round(agent_utilization_rate, 4),
            "task_balance_ratio": round(balance_ratio, 4),
            "load_balance_score": round(balance_ratio, 4),
            "resource_utilization": round(resource_utilization, 4),
            "collaboration_score": round(collaboration_score, 4),
        }

    def _analyze_session(self, session_id: str | None = None) -> dict[str, Any]:
        if not session_id:
            return self._analyze_overall()

        agents_map, messages_list, tasks_list, conflicts_list = self._state_manager.get_snapshot()
        session_info = self._state_manager.get_session_info(session_id)

        communication_analysis = self._analyze_communication(messages_list)
        task_analysis = self._analyze_tasks(tasks_list)
        conflict_analysis = self._analyze_conflicts_for_agents(conflicts_list, None)
        collaboration_analysis = self._analyze_collaboration_quality(
            agents_map=agents_map,
            tasks_len=len(tasks_list),
            messages_len=len(messages_list),
        )

        overall_score = (
            communication_analysis.get("communication_score", 0.5) * 0.3
            + task_analysis.get("task_efficiency_score", 0.5) * 0.3
            + conflict_analysis.get("conflict_resolution_score", 0.5) * 0.2
            + collaboration_analysis.get("collaboration_score", 0.5) * 0.2
        )

        duration_seconds = 0.0
        if session_id in self.collaboration_sessions:
            session_data = self.collaboration_sessions[session_id]
            if "end_time" in session_data and "start_time" in session_data:
                if session_data["end_time"] is not None:
                    duration_seconds = session_data["end_time"] - session_data["start_time"]
                else:
                    duration_seconds = time.time() - session_data["start_time"]
            elif "start_time" in session_data:
                duration_seconds = time.time() - session_data["start_time"]
        elif session_info and "end_time" in session_info and "start_time" in session_info:
            if session_info["end_time"] is not None:
                duration_seconds = session_info["end_time"] - session_info["start_time"]
        elif session_info and "start_time" in session_info:
            duration_seconds = time.time() - session_info["start_time"]

        return {
            "session_id": session_id,
            "session_info": session_info,
            "agents_count": len(agents_map),
            "messages_count": len(messages_list),
            "tasks_count": len(tasks_list),
            "conflicts_count": len(conflicts_list),
            "duration_seconds": duration_seconds,
            "communication": communication_analysis,
            "tasks": task_analysis,
            "conflicts": conflict_analysis,
            "collaboration": collaboration_analysis,
            "overall_score": round(overall_score, 4),
        }

    def _analyze_overall(
        self,
        agents_map: dict[str, AgentInfo] | None = None,
        messages_list: list[AgentMessage] | None = None,
        tasks_list: list[AgentTask] | None = None,
        conflicts_list: list[Conflict] | None = None,
    ) -> dict[str, Any]:
        if agents_map is None:
            agents_map, messages_list, tasks_list, conflicts_list = self._state_manager.get_snapshot()
        if messages_list is None:
            _, messages_list, _, _ = self._state_manager.get_snapshot()
        if tasks_list is None:
            _, _, tasks_list, _ = self._state_manager.get_snapshot()
        if conflicts_list is None:
            _, _, _, conflicts_list = self._state_manager.get_snapshot()

        communication_analysis = self._analyze_communication(messages_list)
        task_analysis = self._analyze_tasks(tasks_list)
        conflict_analysis = self._analyze_conflicts_for_agents(conflicts_list, None)
        collaboration_analysis = self._analyze_collaboration_quality(
            agents_map=agents_map,
            tasks_len=len(tasks_list),
            messages_len=len(messages_list),
        )

        overall_score = (
            communication_analysis.get("communication_score", 0.5) * 0.3
            + task_analysis.get("task_efficiency_score", 0.5) * 0.3
            + conflict_analysis.get("conflict_resolution_score", 0.5) * 0.2
            + collaboration_analysis.get("collaboration_score", 0.5) * 0.2
        )

        return {
            "agents_count": len(agents_map),
            "messages_count": len(messages_list),
            "tasks_count": len(tasks_list),
            "conflicts_count": len(conflicts_list),
            "communication": communication_analysis,
            "tasks": task_analysis,
            "conflicts": conflict_analysis,
            "collaboration": collaboration_analysis,
            "overall_score": round(overall_score, 4),
        }

    def get_agent_info(self, agent_id: str) -> AgentInfo | None:
        return self._state_manager.get_agent_info(agent_id)

    def get_task_info(self, task_id: str) -> AgentTask | None:
        return self._state_manager.get_task_info(task_id)

    def get_conflict_info(self, conflict_id: str) -> Conflict | None:
        return self._state_manager.get_conflict_info(conflict_id)

    def list_agents(self) -> list[str]:
        return self._state_manager.list_agents()

    def list_tasks(self) -> list[str]:
        return self._state_manager.list_tasks()

    def list_conflicts(self) -> list[str]:
        return self._state_manager.list_conflicts()

    def clear_data(self) -> None:
        self._state_manager.clear_data()

    def generate_visualization_report(self, session_id: str | None = None) -> str:
        analysis = self._analyze_session(session_id) if session_id else self._analyze_overall()
        
        html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>多Agent协作评估报告</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f7fa; }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); padding: 30px; }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 25px; }
        .score-card { display: inline-block; background: linear-gradient(135deg, #3498db, #2980b9); color: white; padding: 20px 30px; border-radius: 10px; margin: 10px; }
        .score-value { font-size: 48px; font-weight: bold; }
        .score-label { font-size: 14px; opacity: 0.9; }
        .section { background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 15px 0; }
        .metric-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }
        .metric-name { color: #7f8c8d; }
        .metric-value { font-weight: bold; color: #2c3e50; }
        .bar-container { height: 20px; background: #ecf0f1; border-radius: 10px; overflow: hidden; margin: 5px 0; }
        .bar { height: 100%; border-radius: 10px; transition: width 0.3s; }
        .bar-green { background: #27ae60; }
        .bar-yellow { background: #f39c12; }
        .bar-red { background: #e74c3c; }
        .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
        .stat-box { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 15px; text-align: center; }
        .stat-number { font-size: 24px; font-weight: bold; color: #3498db; }
        .stat-label { font-size: 12px; color: #7f8c8d; }
    </style>
</head>
<body>
    <div class="container">
        <h1>多Agent协作评估报告</h1>
        <div style="margin: 20px 0;">
            <div class="score-card">
                <div class="score-value">{{overall_score}}</div>
                <div class="score-label">综合评分</div>
            </div>
            <div class="score-card" style="background: linear-gradient(135deg, #27ae60, #2ecc71);">
                <div class="score-value">{{comm_score}}</div>
                <div class="score-label">通信质量</div>
            </div>
            <div class="score-card" style="background: linear-gradient(135deg, #f39c12, #e67e22);">
                <div class="score-value">{{task_score}}</div>
                <div class="score-label">任务效率</div>
            </div>
            <div class="score-card" style="background: linear-gradient(135deg, #9b59b6, #8e44ad);">
                <div class="score-value">{{conflict_score}}</div>
                <div class="score-label">冲突解决</div>
            </div>
        </div>
        
        <div class="grid">
            <div class="stat-box">
                <div class="stat-number">{{agents_count}}</div>
                <div class="stat-label">Agent数量</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{messages_count}}</div>
                <div class="stat-label">消息数量</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{tasks_count}}</div>
                <div class="stat-label">任务数量</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{conflicts_count}}</div>
                <div class="stat-label">冲突数量</div>
            </div>
        </div>
        
        <div class="section">
            <h2>通信分析</h2>
            <div class="metric-row"><span class="metric-name">消息总数</span><span class="metric-value">{{comm_total}}</span></div>
            <div class="metric-row"><span class="metric-name">投递率</span><span class="metric-value">{{comm_delivery}}%</span></div>
            <div class="metric-row"><span class="metric-name">确认率</span><span class="metric-value">{{comm_ack}}%</span></div>
            <div class="metric-row"><span class="metric-name">平均延迟</span><span class="metric-value">{{comm_latency}}ms</span></div>
            <div class="bar-container"><div class="bar {{comm_bar_color}}" style="width: {{comm_bar_width}}%"></div></div>
        </div>
        
        <div class="section">
            <h2>任务分析</h2>
            <div class="metric-row"><span class="metric-name">完成率</span><span class="metric-value">{{task_completion}}%</span></div>
            <div class="metric-row"><span class="metric-name">失败率</span><span class="metric-value">{{task_failure}}%</span></div>
            <div class="metric-row"><span class="metric-name">平均完成时间</span><span class="metric-value">{{task_time}}ms</span></div>
            <div class="bar-container"><div class="bar {{task_bar_color}}" style="width: {{task_bar_width}}%"></div></div>
        </div>
        
        <div class="section">
            <h2>冲突分析</h2>
            <div class="metric-row"><span class="metric-name">冲突总数</span><span class="metric-value">{{conflict_total}}</span></div>
            <div class="metric-row"><span class="metric-name">已解决</span><span class="metric-value">{{conflict_resolved}}</span></div>
            <div class="metric-row"><span class="metric-name">解决率</span><span class="metric-value">{{conflict_rate}}%</span></div>
            <div class="bar-container"><div class="bar {{conflict_bar_color}}" style="width: {{conflict_bar_width}}%"></div></div>
        </div>
        
        <div class="section">
            <h2>协作质量</h2>
            <div class="metric-row"><span class="metric-name">Agent利用率</span><span class="metric-value">{{collab_utilization}}%</span></div>
            <div class="metric-row"><span class="metric-name">任务均衡度</span><span class="metric-value">{{collab_balance}}%</span></div>
            <div class="metric-row"><span class="metric-name">资源利用率</span><span class="metric-value">{{collab_resource}}%</span></div>
            <div class="bar-container"><div class="bar {{collab_bar_color}}" style="width: {{collab_bar_width}}%"></div></div>
        </div>
    </div>
</body>
</html>
        """
        
        comm = analysis.get("communication", {})
        task = analysis.get("tasks", {})
        conflict = analysis.get("conflicts", {})
        collab = analysis.get("collaboration", {})
        
        def get_bar_color(score):
            if score >= 0.8: return "bar-green"
            if score >= 0.5: return "bar-yellow"
            return "bar-red"
        
        data = {
            "overall_score": f"{analysis.get('overall_score', 0):.2f}",
            "comm_score": f"{comm.get('communication_score', 0):.2f}",
            "task_score": f"{task.get('task_efficiency_score', 0):.2f}",
            "conflict_score": f"{conflict.get('conflict_resolution_score', 0):.2f}",
            "agents_count": analysis.get("agents_count", 0),
            "messages_count": analysis.get("messages_count", 0),
            "tasks_count": analysis.get("tasks_count", 0),
            "conflicts_count": analysis.get("conflicts_count", 0),
            "comm_total": comm.get("total_messages", 0),
            "comm_delivery": f"{comm.get('delivery_rate', 0) * 100:.1f}",
            "comm_ack": f"{comm.get('acknowledgment_rate', 0) * 100:.1f}",
            "comm_latency": comm.get("avg_latency_ms", 0),
            "comm_bar_color": get_bar_color(comm.get("communication_score", 0)),
            "comm_bar_width": f"{comm.get('communication_score', 0) * 100:.1f}",
            "task_completion": f"{task.get('completion_rate', 0) * 100:.1f}",
            "task_failure": f"{task.get('failure_rate', 0) * 100:.1f}",
            "task_time": task.get("avg_completion_time_ms", 0),
            "task_bar_color": get_bar_color(task.get("task_efficiency_score", 0)),
            "task_bar_width": f"{task.get('task_efficiency_score', 0) * 100:.1f}",
            "conflict_total": conflict.get("total_conflicts", 0),
            "conflict_resolved": conflict.get("resolved_conflicts", 0),
            "conflict_rate": f"{conflict.get('resolution_rate', 0) * 100:.1f}",
            "conflict_bar_color": get_bar_color(conflict.get("conflict_resolution_score", 0)),
            "conflict_bar_width": f"{conflict.get('conflict_resolution_score', 0) * 100:.1f}",
            "collab_utilization": f"{collab.get('agent_utilization_rate', 0) * 100:.1f}",
            "collab_balance": f"{collab.get('task_balance_ratio', 0) * 100:.1f}",
            "collab_resource": f"{collab.get('resource_utilization', 0) * 100:.1f}",
            "collab_bar_color": get_bar_color(collab.get("collaboration_score", 0)),
            "collab_bar_width": f"{collab.get('collaboration_score', 0) * 100:.1f}",
        }
        
        return html_template.format(**data)

    @property
    def agents(self):
        return self._state_manager.agents

    @agents.setter
    def agents(self, value):
        self._state_manager.agents = value

    @property
    def conflicts(self):
        return self._state_manager.conflicts

    @conflicts.setter
    def conflicts(self, value):
        self._state_manager.conflicts = value

    @property
    def tasks(self):
        return self._state_manager.tasks

    @tasks.setter
    def tasks(self, value):
        self._state_manager.tasks = value

    @property
    def messages(self):
        return self._state_manager.messages

    @messages.setter
    def messages(self, value):
        self._state_manager.messages = value
