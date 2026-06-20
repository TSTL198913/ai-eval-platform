"""多Agent协作评估器

用于评估多Agent系统中的协作效率和质量，包括：
- Agent间通信质量评估
- 任务分配效率评估
- 协作完成率评估
- 冲突检测评估
"""

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    清理用户输入，防止XSS和注入攻击

    Args:
        text: 用户输入文本
        max_length: 最大允许长度

    Returns:
        清理后的安全文本
    """
    if not text:
        return ""

    # 限制长度
    text = text[:max_length]

    # 移除潜在危险的HTML标签和脚本
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)  # 移除所有HTML标签

    # 移除潜在危险的字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)  # 控制字符

    return text.strip()


class MessageType(str, Enum):
    """消息类型枚举"""
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    NOTIFICATION = "notification"
    ERROR = "error"


class ConflictType(str, Enum):
    """冲突类型枚举"""
    RESOURCE = "resource"
    TASK = "task"
    COMMUNICATION = "communication"
    PRIORITY = "priority"
    DATA = "data"


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentMessage:
    """Agent间消息"""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    content: str
    timestamp: float
    latency_ms: float = 0.0
    is_delivered: bool = True
    is_acknowledged: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentTask:
    """Agent任务"""
    task_id: str
    agent_id: str
    description: str
    status: TaskStatus
    priority: int = 1
    assigned_at: float = 0.0
    completed_at: float = 0.0
    dependencies: list[str] = field(default_factory=list)
    result: Any = None
    error: str | None = None


@dataclass
class Conflict:
    """冲突记录"""
    conflict_id: str
    conflict_type: ConflictType
    agent_ids: list[str]
    description: str
    timestamp: float
    resolved: bool = False
    resolution: str | None = None


@dataclass
class AgentInfo:
    """Agent信息"""
    agent_id: str
    role: str
    capabilities: list[str] = field(default_factory=list)
    status: str = "active"
    current_tasks: list[str] = field(default_factory=list)
    message_count: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0


@EvaluatorFactory.register("multi_agent")
class MultiAgentEvaluator(BaseEvaluator):
    """多Agent协作评估器

    评估多Agent系统中的协作效率和质量，支持：
    - Agent间通信质量评估
    - 任务分配效率评估
    - 协作完成率评估
    - 冲突检测评估
    """

    def __init__(self, client=None):
        super().__init__(client)
        self.agents: dict[str, AgentInfo] = {}
        self.messages: list[AgentMessage] = []
        self.tasks: dict[str, AgentTask] = {}
        self.conflicts: list[Conflict] = []
        self.collaboration_sessions: dict[str, dict] = {}

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """评估多Agent协作结果"""
        action = self.get_payload_data(request, "action", "evaluate")

        if action == "register_agent":
            return self._register_agent(request)
        elif action == "record_message":
            return self._record_message(request)
        elif action == "assign_task":
            return self._assign_task(request)
        elif action == "update_task":
            return self._update_task(request)
        elif action == "record_conflict":
            return self._record_conflict(request)
        elif action == "resolve_conflict":
            return self._resolve_conflict(request)
        elif action == "start_session":
            return self._start_collaboration_session(request)
        elif action == "end_session":
            return self._end_collaboration_session(request)
        elif action == "analyze":
            return self._analyze_collaboration(request)
        else:
            return self._evaluate_collaboration(request)

    def _register_agent(self, request: EvaluationSchema) -> DomainResponse:
        """注册Agent"""
        agent_id = self.get_payload_data(request, "agent_id")
        role = self.get_payload_data(request, "role", "worker")
        capabilities = self.get_payload_data(request, "capabilities", [])

        if not agent_id:
            return DomainResponse(
                is_valid=False,
                error="agent_id 不能为空"
            )

        agent = AgentInfo(
            agent_id=agent_id,
            role=role,
            capabilities=capabilities,
        )
        self.agents[agent_id] = agent

        return DomainResponse(
            is_valid=True,
            text=f"Agent {agent_id} 注册成功",
            score=1.0,
            data={
                "agent_id": agent_id,
                "role": role,
                "capabilities": capabilities,
            }
        )

    def _record_message(self, request: EvaluationSchema) -> DomainResponse:
        """记录Agent间消息"""
        message_id = self.get_payload_data(request, "message_id")
        sender_id = self.get_payload_data(request, "sender_id")
        receiver_id = self.get_payload_data(request, "receiver_id")
        message_type = self.get_payload_data(request, "message_type", "request")
        content = sanitize_input(self.get_payload_data(request, "content", ""))
        latency_ms = self.get_payload_data(request, "latency_ms", 0.0)
        is_delivered = self.get_payload_data(request, "is_delivered", True)
        is_acknowledged = self.get_payload_data(request, "is_acknowledged", False)
        metadata = self.get_payload_data(request, "metadata", {})

        if not sender_id or not receiver_id:
            return DomainResponse(
                is_valid=False,
                error="sender_id 和 receiver_id 不能为空"
            )

        # 安全处理枚举值
        try:
            msg_type = MessageType(message_type)
        except ValueError:
            return DomainResponse(
                is_valid=False,
                error=f"无效的message_type: {message_type}"
            )

        message = AgentMessage(
            message_id=message_id or f"msg-{len(self.messages)}",
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=msg_type,
            content=content,
            timestamp=time.time(),
            latency_ms=latency_ms,
            is_delivered=is_delivered,
            is_acknowledged=is_acknowledged,
            metadata=metadata,
        )
        self.messages.append(message)

        # 更新Agent消息计数
        if sender_id in self.agents:
            self.agents[sender_id].message_count += 1

        return DomainResponse(
            is_valid=True,
            text="消息记录成功",
            score=1.0,
            data={
                "message_id": message.message_id,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "message_type": message_type,
            }
        )

    def _assign_task(self, request: EvaluationSchema) -> DomainResponse:
        """分配任务给Agent"""
        task_id = self.get_payload_data(request, "task_id")
        agent_id = self.get_payload_data(request, "agent_id")
        description = sanitize_input(self.get_payload_data(request, "description", ""))
        priority = self.get_payload_data(request, "priority", 1)
        dependencies = self.get_payload_data(request, "dependencies", [])

        if not task_id or not agent_id:
            return DomainResponse(
                is_valid=False,
                error="task_id 和 agent_id 不能为空"
            )

        if agent_id not in self.agents:
            return DomainResponse(
                is_valid=False,
                error=f"Agent {agent_id} 未注册"
            )

        task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            description=description,
            status=TaskStatus.ASSIGNED,
            priority=priority,
            assigned_at=time.time(),
            dependencies=dependencies,
        )
        self.tasks[task_id] = task
        self.agents[agent_id].current_tasks.append(task_id)

        return DomainResponse(
            is_valid=True,
            text=f"任务 {task_id} 已分配给 Agent {agent_id}",
            score=1.0,
            data={
                "task_id": task_id,
                "agent_id": agent_id,
                "status": "assigned",
            }
        )

    def _update_task(self, request: EvaluationSchema) -> DomainResponse:
        """更新任务状态"""
        task_id = self.get_payload_data(request, "task_id")
        status = self.get_payload_data(request, "status")
        result = self.get_payload_data(request, "result")
        error = sanitize_input(self.get_payload_data(request, "error", ""))

        if task_id not in self.tasks:
            return DomainResponse(
                is_valid=False,
                error=f"任务 {task_id} 不存在"
            )

        # 安全处理枚举值
        try:
            new_status = TaskStatus(status)
        except ValueError:
            return DomainResponse(
                is_valid=False,
                error=f"无效的status: {status}"
            )

        task = self.tasks[task_id]
        old_status = task.status
        task.status = new_status

        if task.status == TaskStatus.COMPLETED:
            task.completed_at = time.time()
            task.result = result
            if task.agent_id in self.agents:
                self.agents[task.agent_id].completed_tasks += 1
                if task_id in self.agents[task.agent_id].current_tasks:
                    self.agents[task.agent_id].current_tasks.remove(task_id)
        elif task.status == TaskStatus.FAILED:
            task.error = error
            if task.agent_id in self.agents:
                self.agents[task.agent_id].failed_tasks += 1
                if task_id in self.agents[task.agent_id].current_tasks:
                    self.agents[task.agent_id].current_tasks.remove(task_id)

        return DomainResponse(
            is_valid=True,
            text=f"任务 {task_id} 状态已更新为 {status}",
            score=1.0,
            data={
                "task_id": task_id,
                "old_status": old_status.value,
                "new_status": status,
            }
        )

    def _record_conflict(self, request: EvaluationSchema) -> DomainResponse:
        """记录冲突"""
        conflict_id = self.get_payload_data(request, "conflict_id")
        conflict_type = self.get_payload_data(request, "conflict_type")
        agent_ids = self.get_payload_data(request, "agent_ids", [])
        description = sanitize_input(self.get_payload_data(request, "description", ""))

        if not agent_ids:
            return DomainResponse(
                is_valid=False,
                error="agent_ids 不能为空"
            )

        # 安全处理枚举值
        try:
            conflict_type_enum = ConflictType(conflict_type)
        except ValueError:
            return DomainResponse(
                is_valid=False,
                error=f"无效的conflict_type: {conflict_type}"
            )

        conflict = Conflict(
            conflict_id=conflict_id or f"conflict-{len(self.conflicts)}",
            conflict_type=conflict_type_enum,
            agent_ids=agent_ids,
            description=description,
            timestamp=time.time(),
        )
        self.conflicts.append(conflict)

        return DomainResponse(
            is_valid=True,
            text="冲突已记录",
            score=1.0,
            data={
                "conflict_id": conflict.conflict_id,
                "conflict_type": conflict_type,
                "agent_ids": agent_ids,
            }
        )

    def _resolve_conflict(self, request: EvaluationSchema) -> DomainResponse:
        """解决冲突"""
        conflict_id = self.get_payload_data(request, "conflict_id")
        resolution = sanitize_input(self.get_payload_data(request, "resolution", ""))

        conflict = None
        for c in self.conflicts:
            if c.conflict_id == conflict_id:
                conflict = c
                break

        if not conflict:
            return DomainResponse(
                is_valid=False,
                error=f"冲突 {conflict_id} 不存在"
            )

        conflict.resolved = True
        conflict.resolution = resolution

        return DomainResponse(
            is_valid=True,
            text=f"冲突 {conflict_id} 已解决",
            score=1.0,
            data={
                "conflict_id": conflict_id,
                "resolution": resolution,
            }
        )

    def _start_collaboration_session(self, request: EvaluationSchema) -> DomainResponse:
        """开始协作会话"""
        session_id = self.get_payload_data(request, "session_id")
        agent_ids = self.get_payload_data(request, "agent_ids", [])
        goal = self.get_payload_data(request, "goal", "")

        if not session_id:
            return DomainResponse(
                is_valid=False,
                error="session_id 不能为空"
            )

        self.collaboration_sessions[session_id] = {
            "session_id": session_id,
            "agent_ids": agent_ids,
            "goal": goal,
            "start_time": time.time(),
            "end_time": None,
            "status": "active",
            "messages": [],
            "tasks": [],
        }

        return DomainResponse(
            is_valid=True,
            text=f"协作会话 {session_id} 已开始",
            score=1.0,
            data={
                "session_id": session_id,
                "agent_ids": agent_ids,
                "goal": goal,
            }
        )

    def _end_collaboration_session(self, request: EvaluationSchema) -> DomainResponse:
        """结束协作会话"""
        session_id = self.get_payload_data(request, "session_id")
        status = self.get_payload_data(request, "status", "completed")

        if session_id not in self.collaboration_sessions:
            return DomainResponse(
                is_valid=False,
                error=f"会话 {session_id} 不存在"
            )

        session = self.collaboration_sessions[session_id]
        session["end_time"] = time.time()
        session["status"] = status

        return DomainResponse(
            is_valid=True,
            text=f"协作会话 {session_id} 已结束",
            score=1.0,
            data={
                "session_id": session_id,
                "status": status,
                "duration_seconds": session["end_time"] - session["start_time"],
            }
        )

    def _analyze_collaboration(self, request: EvaluationSchema) -> DomainResponse:
        """分析协作数据"""
        session_id = self.get_payload_data(request, "session_id")

        if session_id and session_id in self.collaboration_sessions:
            analysis = self._analyze_session(session_id)
        else:
            analysis = self._analyze_overall()

        return DomainResponse(
            is_valid=True,
            text="协作分析完成",
            score=analysis.get("overall_score", 0.5),
            data=analysis,
        )

    def _evaluate_collaboration(self, request: EvaluationSchema) -> DomainResponse:
        """评估多Agent协作"""
        # 从请求中获取协作数据
        agents_data = self.get_payload_data(request, "agents", [])
        messages_data = self.get_payload_data(request, "messages", [])
        tasks_data = self.get_payload_data(request, "tasks", [])
        conflicts_data = self.get_payload_data(request, "conflicts", [])

        # 临时存储协作数据
        temp_agents = dict(self.agents)
        temp_messages = list(self.messages)
        temp_tasks = dict(self.tasks)
        temp_conflicts = list(self.conflicts)

        # 导入请求数据
        self._import_collaboration_data(agents_data, messages_data, tasks_data, conflicts_data)

        # 执行分析
        analysis = self._analyze_overall()

        # 恢复原数据
        self.agents = temp_agents
        self.messages = temp_messages
        self.tasks = temp_tasks
        self.conflicts = temp_conflicts

        return DomainResponse(
            is_valid=True,
            text="多Agent协作评估完成",
            score=analysis.get("overall_score", 0.5),
            data=analysis,
        )

    def _import_collaboration_data(
        self,
        agents_data: list[dict],
        messages_data: list[dict],
        tasks_data: list[dict],
        conflicts_data: list[dict],
    ):
        """导入协作数据"""
        self.agents.clear()
        self.messages.clear()
        self.tasks.clear()
        self.conflicts.clear()

        for agent_data in agents_data:
            agent = AgentInfo(
                agent_id=agent_data.get("agent_id"),
                role=agent_data.get("role", "worker"),
                capabilities=agent_data.get("capabilities", []),
                status=agent_data.get("status", "active"),
                message_count=agent_data.get("message_count", 0),
                completed_tasks=agent_data.get("completed_tasks", 0),
                failed_tasks=agent_data.get("failed_tasks", 0),
            )
            self.agents[agent.agent_id] = agent

        for msg_data in messages_data:
            message = AgentMessage(
                message_id=msg_data.get("message_id", f"msg-{len(self.messages)}"),
                sender_id=msg_data.get("sender_id"),
                receiver_id=msg_data.get("receiver_id"),
                message_type=MessageType(msg_data.get("message_type", "request")),
                content=msg_data.get("content", ""),
                timestamp=msg_data.get("timestamp", time.time()),
                latency_ms=msg_data.get("latency_ms", 0.0),
                is_delivered=msg_data.get("is_delivered", True),
                is_acknowledged=msg_data.get("is_acknowledged", False),
            )
            self.messages.append(message)

        for task_data in tasks_data:
            task = AgentTask(
                task_id=task_data.get("task_id"),
                agent_id=task_data.get("agent_id"),
                description=task_data.get("description", ""),
                status=TaskStatus(task_data.get("status", "pending")),
                priority=task_data.get("priority", 1),
                assigned_at=task_data.get("assigned_at", 0.0),
                completed_at=task_data.get("completed_at", 0.0),
                dependencies=task_data.get("dependencies", []),
                result=task_data.get("result"),
                error=task_data.get("error"),
            )
            self.tasks[task.task_id] = task

        for conflict_data in conflicts_data:
            conflict = Conflict(
                conflict_id=conflict_data.get("conflict_id", f"conflict-{len(self.conflicts)}"),
                conflict_type=ConflictType(conflict_data.get("conflict_type", "task")),
                agent_ids=conflict_data.get("agent_ids", []),
                description=conflict_data.get("description", ""),
                timestamp=conflict_data.get("timestamp", time.time()),
                resolved=conflict_data.get("resolved", False),
                resolution=conflict_data.get("resolution"),
            )
            self.conflicts.append(conflict)

    def _analyze_session(self, session_id: str) -> dict:
        """分析特定协作会话"""
        session = self.collaboration_sessions.get(session_id)
        if not session:
            return {"error": f"会话 {session_id} 不存在"}

        # 获取会话相关的消息和任务
        session_messages = [m for m in self.messages if m.sender_id in session["agent_ids"] or m.receiver_id in session["agent_ids"]]
        session_tasks = [t for t in self.tasks.values() if t.agent_id in session["agent_ids"]]

        communication_analysis = self._analyze_communication(session_messages)
        task_analysis = self._analyze_tasks(session_tasks)
        conflict_analysis = self._analyze_conflicts_for_agents(session["agent_ids"])

        overall_score = (
            communication_analysis.get("communication_score", 0.5) * 0.3 +
            task_analysis.get("task_efficiency_score", 0.5) * 0.4 +
            conflict_analysis.get("conflict_resolution_score", 0.5) * 0.3
        )

        return {
            "session_id": session_id,
            "communication": communication_analysis,
            "tasks": task_analysis,
            "conflicts": conflict_analysis,
            "overall_score": overall_score,
            "duration_seconds": (session.get("end_time") or time.time()) - session["start_time"],
        }

    def _analyze_overall(self) -> dict:
        """整体协作分析"""
        communication_analysis = self._analyze_communication(self.messages)
        task_analysis = self._analyze_tasks(list(self.tasks.values()))
        conflict_analysis = self._analyze_conflicts()
        collaboration_analysis = self._analyze_collaboration_quality()

        overall_score = (
            communication_analysis.get("communication_score", 0.5) * 0.25 +
            task_analysis.get("task_efficiency_score", 0.5) * 0.35 +
            conflict_analysis.get("conflict_resolution_score", 0.5) * 0.2 +
            collaboration_analysis.get("collaboration_score", 0.5) * 0.2
        )

        return {
            "agents_count": len(self.agents),
            "messages_count": len(self.messages),
            "tasks_count": len(self.tasks),
            "conflicts_count": len(self.conflicts),
            "communication": communication_analysis,
            "tasks": task_analysis,
            "conflicts": conflict_analysis,
            "collaboration": collaboration_analysis,
            "overall_score": overall_score,
        }

    def _analyze_communication(self, messages: list[AgentMessage]) -> dict:
        """分析通信质量"""
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

        delivery_rate = delivered_messages / total_messages if total_messages > 0 else 0.0
        acknowledgment_rate = acknowledged_messages / total_messages if total_messages > 0 else 0.0

        latencies = [m.latency_ms for m in messages if m.latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        # 消息类型分布
        type_distribution = {}
        for msg in messages:
            msg_type = msg.message_type.value
            type_distribution[msg_type] = type_distribution.get(msg_type, 0) + 1

        # 计算通信质量分数
        # 考虑投递率、确认率和延迟
        latency_score = max(0.0, min(1.0, 1.0 - (avg_latency / 1000.0))) if avg_latency > 0 else 1.0
        communication_score = (
            delivery_rate * 0.4 +
            acknowledgment_rate * 0.3 +
            latency_score * 0.3
        )

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

    def _analyze_tasks(self, tasks: list[AgentTask]) -> dict:
        """分析任务分配效率"""
        if not tasks:
            return {
                "total_tasks": 0,
                "completion_rate": 0.0,
                "failure_rate": 0.0,
                "avg_completion_time_ms": 0.0,
                "task_efficiency_score": 0.5,
            }

        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed_tasks = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        pending_tasks = sum(1 for t in tasks if t.status in [TaskStatus.PENDING, TaskStatus.ASSIGNED])

        completion_rate = completed_tasks / total_tasks if total_tasks > 0 else 0.0
        failure_rate = failed_tasks / total_tasks if total_tasks > 0 else 0.0

        # 计算平均完成时间
        completion_times = []
        for task in tasks:
            if task.status == TaskStatus.COMPLETED and task.completed_at > 0 and task.assigned_at > 0:
                completion_times.append((task.completed_at - task.assigned_at) * 1000)

        avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0.0

        # 计算任务效率分数
        # 考虑完成率、失败率和完成时间
        time_score = max(0.0, min(1.0, 1.0 - (avg_completion_time / 10000.0))) if avg_completion_time > 0 else 1.0
        task_efficiency_score = (
            completion_rate * 0.5 +
            (1.0 - failure_rate) * 0.3 +
            time_score * 0.2
        )

        # 按Agent统计任务分配
        agent_task_distribution = {}
        for task in tasks:
            agent_id = task.agent_id
            if agent_id not in agent_task_distribution:
                agent_task_distribution[agent_id] = {"total": 0, "completed": 0, "failed": 0}
            agent_task_distribution[agent_id]["total"] += 1
            if task.status == TaskStatus.COMPLETED:
                agent_task_distribution[agent_id]["completed"] += 1
            elif task.status == TaskStatus.FAILED:
                agent_task_distribution[agent_id]["failed"] += 1

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "pending_tasks": pending_tasks,
            "completion_rate": round(completion_rate, 4),
            "failure_rate": round(failure_rate, 4),
            "avg_completion_time_ms": round(avg_completion_time, 2),
            "agent_task_distribution": agent_task_distribution,
            "task_efficiency_score": round(task_efficiency_score, 4),
        }

    def _analyze_conflicts(self) -> dict:
        """分析冲突情况"""
        return self._analyze_conflicts_for_agents(None)

    def _analyze_conflicts_for_agents(self, agent_ids: list[str] | None) -> dict:
        """分析特定Agent的冲突情况"""
        if agent_ids:
            conflicts = [c for c in self.conflicts if any(aid in c.agent_ids for aid in agent_ids)]
        else:
            conflicts = self.conflicts

        if not conflicts:
            return {
                "total_conflicts": 0,
                "resolved_conflicts": 0,
                "unresolved_conflicts": 0,
                "resolution_rate": 0.0,
                "conflict_type_distribution": {},
                "conflict_resolution_score": 1.0,
            }

        total_conflicts = len(conflicts)
        resolved_conflicts = sum(1 for c in conflicts if c.resolved)
        unresolved_conflicts = total_conflicts - resolved_conflicts

        resolution_rate = resolved_conflicts / total_conflicts if total_conflicts > 0 else 0.0

        # 冲突类型分布
        type_distribution = {}
        for conflict in conflicts:
            c_type = conflict.conflict_type.value
            type_distribution[c_type] = type_distribution.get(c_type, 0) + 1

        # 计算冲突解决分数
        # 冲突越少且解决率越高，分数越高
        conflict_penalty = min(1.0, total_conflicts / 10.0)  # 每10个冲突扣1分
        conflict_resolution_score = resolution_rate * (1.0 - conflict_penalty * 0.5)

        return {
            "total_conflicts": total_conflicts,
            "resolved_conflicts": resolved_conflicts,
            "unresolved_conflicts": unresolved_conflicts,
            "resolution_rate": round(resolution_rate, 4),
            "conflict_type_distribution": type_distribution,
            "conflict_resolution_score": round(max(0.0, conflict_resolution_score), 4),
        }

    def _analyze_collaboration_quality(self) -> dict:
        """分析协作质量"""
        if not self.agents:
            return {
                "active_agents": 0,
                "avg_tasks_per_agent": 0.0,
                "avg_messages_per_agent": 0.0,
                "agent_utilization_rate": 0.0,
                "collaboration_score": 0.5,
            }

        total_agents = len(self.agents)
        active_agents = sum(1 for a in self.agents.values() if a.status == "active")

        total_tasks = len(self.tasks)
        total_messages = len(self.messages)

        avg_tasks_per_agent = total_tasks / total_agents if total_agents > 0 else 0.0
        avg_messages_per_agent = total_messages / total_agents if total_agents > 0 else 0.0

        # Agent利用率：有任务的Agent比例
        agents_with_tasks = sum(1 for a in self.agents.values() if a.completed_tasks > 0 or len(a.current_tasks) > 0)
        agent_utilization_rate = agents_with_tasks / total_agents if total_agents > 0 else 0.0

        # 协作分数计算
        # 考虑Agent活跃度、利用率和负载均衡
        activity_score = active_agents / total_agents if total_agents > 0 else 0.0

        # 负载均衡分数：任务分配的均匀程度
        task_counts = [a.completed_tasks + len(a.current_tasks) for a in self.agents.values()]
        if task_counts and max(task_counts) > 0:
            avg_tasks = sum(task_counts) / len(task_counts)
            variance = sum((t - avg_tasks) ** 2 for t in task_counts) / len(task_counts)
            load_balance_score = max(0.0, 1.0 - (variance / (max(task_counts) ** 2)))
        else:
            load_balance_score = 1.0

        collaboration_score = (
            activity_score * 0.3 +
            agent_utilization_rate * 0.4 +
            load_balance_score * 0.3
        )

        return {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "agents_with_tasks": agents_with_tasks,
            "avg_tasks_per_agent": round(avg_tasks_per_agent, 2),
            "avg_messages_per_agent": round(avg_messages_per_agent, 2),
            "agent_utilization_rate": round(agent_utilization_rate, 4),
            "load_balance_score": round(load_balance_score, 4),
            "collaboration_score": round(collaboration_score, 4),
        }

    def get_agent_info(self, agent_id: str) -> AgentInfo | None:
        """获取Agent信息"""
        return self.agents.get(agent_id)

    def get_task_info(self, task_id: str) -> AgentTask | None:
        """获取任务信息"""
        return self.tasks.get(task_id)

    def get_conflict_info(self, conflict_id: str) -> Conflict | None:
        """获取冲突信息"""
        for conflict in self.conflicts:
            if conflict.conflict_id == conflict_id:
                return conflict
        return None

    def list_agents(self) -> list[str]:
        """列出所有Agent"""
        return list(self.agents.keys())

    def list_tasks(self) -> list[str]:
        """列出所有任务"""
        return list(self.tasks.keys())

    def list_conflicts(self) -> list[str]:
        """列出所有冲突"""
        return [c.conflict_id for c in self.conflicts]

    def clear_data(self):
        """清空所有数据"""
        self.agents.clear()
        self.messages.clear()
        self.tasks.clear()
        self.conflicts.clear()
        self.collaboration_sessions.clear()
