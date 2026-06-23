"""多Agent协作评估器

用于评估多Agent系统中的协作效率和质量，包括：
- Agent间通信质量评估
- 任务分配效率评估
- 协作完成率评估
- 冲突检测评估
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# 假设的基础依赖导入路径
from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema

# 设置工业级结构化日志
logger = logging.getLogger(__name__)

# 预编译安全过滤正则，提升高频调用下的 CPU 性能并防止 ReDoS
_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_HTML_RE = re.compile(r"<[^>]+>")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """清理用户输入，防止 XSS 和注入攻击（高性能预编译版）"""
    if not text:
        return ""

    text = text[:max_length]
    text = _SCRIPT_RE.sub("", text)
    text = _HTML_RE.sub("", text)
    text = _CONTROL_CHAR_RE.sub("", text)
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


# 开启 slots=True 显著降低高吞吐智能体轨迹序列化的内存占用
@dataclass(slots=True)
class AgentMessage:
    """Agent间消息模型"""

    message_id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    content: str
    timestamp: float
    latency_ms: float = 0.0
    is_delivered: bool = True
    is_acknowledged: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentTask:
    """Agent任务模型"""

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


@dataclass(slots=True)
class Conflict:
    """冲突记录模型"""

    conflict_id: str
    conflict_type: ConflictType
    agent_ids: list[str]
    description: str
    timestamp: float
    resolved: bool = False
    resolution: str | None = None


@dataclass(slots=True)
class AgentInfo:
    """Agent信息统计模型"""

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
    """多Agent协作评估器 (2026 工业级高并发版)"""

    def __init__(self, client=None):
        super().__init__(client)
        # 细粒度独立线程锁，最大化并发吞吐性能
        self._agents_lock = threading.Lock()
        self._messages_lock = threading.Lock()
        self._tasks_lock = threading.Lock()
        self._conflicts_lock = threading.Lock()
        self._sessions_lock = threading.Lock()

        # 内存数据存储群
        self.agents: dict[str, AgentInfo] = {}
        self.messages: list[AgentMessage] = []
        self.tasks: dict[str, AgentTask] = {}
        self.conflicts: list[Conflict] = []
        self.collaboration_sessions: dict[str, dict[str, Any]] = {}

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """评估入口（采用现代 Python 模式匹配 match-case 路由）"""
        action = self.get_payload_data(request, "action", "evaluate")
        logger.debug(f"MultiAgentEvaluator 正在执行动作: {action}")

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
        """注册 Agent"""
        agent_id = self.get_payload_data(request, "agent_id")
        role = self.get_payload_data(request, "role", "worker")
        capabilities = self.get_payload_data(request, "capabilities", [])

        if not agent_id:
            return DomainResponse(is_valid=False, error="agent_id 不能为空")

        agent = AgentInfo(agent_id=agent_id, role=role, capabilities=capabilities)
        with self._agents_lock:
            self.agents[agent_id] = agent

        return DomainResponse(
            is_valid=True,
            text=f"Agent {agent_id} 注册成功",
            score=1.0,
            data={"agent_id": agent_id, "role": role, "capabilities": capabilities},
        )

    def _record_message(self, request: EvaluationSchema) -> DomainResponse:
        """记录 Agent 间消息"""
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
            return DomainResponse(is_valid=False, error="sender_id 和 receiver_id 不能为空")

        try:
            msg_type = MessageType(message_type)
        except ValueError:
            return DomainResponse(is_valid=False, error=f"无效的 message_type: {message_type}")

        with self._messages_lock:
            msg_id = message_id or f"msg-{len(self.messages)}"
            message = AgentMessage(
                message_id=msg_id,
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

        with self._agents_lock:
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
            },
        )

    def _assign_task(self, request: EvaluationSchema) -> DomainResponse:
        """分配任务给 Agent"""
        task_id = self.get_payload_data(request, "task_id")
        agent_id = self.get_payload_data(request, "agent_id")
        description = sanitize_input(self.get_payload_data(request, "description", ""))
        priority = self.get_payload_data(request, "priority", 1)
        dependencies = self.get_payload_data(request, "dependencies", [])

        if not task_id or not agent_id:
            return DomainResponse(is_valid=False, error="task_id 和 agent_id 不能为空")

        with self._agents_lock:
            if agent_id not in self.agents:
                return DomainResponse(is_valid=False, error=f"Agent {agent_id} 未注册")

        task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            description=description,
            status=TaskStatus.ASSIGNED,
            priority=priority,
            assigned_at=time.time(),
            dependencies=dependencies,
        )

        with self._tasks_lock:
            self.tasks[task_id] = task
        with self._agents_lock:
            self.agents[agent_id].current_tasks.append(task_id)

        return DomainResponse(
            is_valid=True,
            text=f"任务 {task_id} 已分配给 Agent {agent_id}",
            score=1.0,
            data={"task_id": task_id, "agent_id": agent_id, "status": "assigned"},
        )

    def _update_task(self, request: EvaluationSchema) -> DomainResponse:
        """更新任务状态"""
        task_id = self.get_payload_data(request, "task_id")
        status = self.get_payload_data(request, "status")
        result = self.get_payload_data(request, "result")
        error = sanitize_input(self.get_payload_data(request, "error", ""))

        try:
            new_status = TaskStatus(status)
        except ValueError:
            return DomainResponse(is_valid=False, error=f"无效的 status: {status}")

        with self._tasks_lock:
            if task_id not in self.tasks:
                return DomainResponse(is_valid=False, error=f"任务 {task_id} 不存在")
            task = self.tasks[task_id]
            old_status = task.status
            task.status = new_status

            if task.status == TaskStatus.COMPLETED:
                task.completed_at = time.time()
                task.result = result
                agent_id = task.agent_id
            elif task.status == TaskStatus.FAILED:
                task.error = error
                agent_id = task.agent_id
            else:
                agent_id = None

        if agent_id:
            with self._agents_lock:
                if agent_id in self.agents:
                    agent_info = self.agents[agent_id]
                    if new_status == TaskStatus.COMPLETED:
                        agent_info.completed_tasks += 1
                    elif new_status == TaskStatus.FAILED:
                        agent_info.failed_tasks += 1
                    if task_id in agent_info.current_tasks:
                        agent_info.current_tasks.remove(task_id)

        return DomainResponse(
            is_valid=True,
            text=f"任务 {task_id} 状态已更新为 {status}",
            score=1.0,
            data={"task_id": task_id, "old_status": old_status.value, "new_status": status},
        )

    def _record_conflict(self, request: EvaluationSchema) -> DomainResponse:
        """记录冲突"""
        conflict_id = self.get_payload_data(request, "conflict_id")
        conflict_type = self.get_payload_data(request, "conflict_type")
        agent_ids = self.get_payload_data(request, "agent_ids", [])
        description = sanitize_input(self.get_payload_data(request, "description", ""))

        if not agent_ids:
            return DomainResponse(is_valid=False, error="agent_ids 不能为空")

        try:
            conflict_type_enum = ConflictType(conflict_type)
        except ValueError:
            return DomainResponse(is_valid=False, error=f"无效的 conflict_type: {conflict_type}")

        with self._conflicts_lock:
            c_id = conflict_id or f"conflict-{len(self.conflicts)}"
            conflict = Conflict(
                conflict_id=c_id,
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
            },
        )

    def _resolve_conflict(self, request: EvaluationSchema) -> DomainResponse:
        """解决冲突"""
        conflict_id = self.get_payload_data(request, "conflict_id")
        resolution = sanitize_input(self.get_payload_data(request, "resolution", ""))

        conflict = None
        with self._conflicts_lock:
            for c in self.conflicts:
                if c.conflict_id == conflict_id:
                    conflict = c
                    break

            if not conflict:
                return DomainResponse(is_valid=False, error=f"冲突 {conflict_id} 不存在")

            conflict.resolved = True
            conflict.resolution = resolution

        return DomainResponse(
            is_valid=True,
            text=f"冲突 {conflict_id} 已解决",
            score=1.0,
            data={"conflict_id": conflict_id, "resolution": resolution},
        )

    def _start_collaboration_session(self, request: EvaluationSchema) -> DomainResponse:
        """开始协作会话"""
        session_id = self.get_payload_data(request, "session_id")
        agent_ids = self.get_payload_data(request, "agent_ids", [])
        goal = self.get_payload_data(request, "goal", "")

        if not session_id:
            return DomainResponse(is_valid=False, error="session_id 不能为空")

        with self._sessions_lock:
            self.collaboration_sessions[session_id] = {
                "session_id": session_id,
                "agent_ids": agent_ids,
                "goal": goal,
                "start_time": time.time(),
                "end_time": None,
                "status": "active",
            }

        return DomainResponse(
            is_valid=True,
            text=f"协作会话 {session_id} 已开始",
            score=1.0,
            data={"session_id": session_id, "agent_ids": agent_ids, "goal": goal},
        )

    def _end_collaboration_session(self, request: EvaluationSchema) -> DomainResponse:
        """结束协作会话"""
        session_id = self.get_payload_data(request, "session_id")
        status = self.get_payload_data(request, "status", "completed")

        with self._sessions_lock:
            if session_id not in self.collaboration_sessions:
                return DomainResponse(is_valid=False, error=f"会话 {session_id} 不存在")

            session = self.collaboration_sessions[session_id]
            session["end_time"] = time.time()
            session["status"] = status
            duration_seconds = session["end_time"] - session["start_time"]

        return DomainResponse(
            is_valid=True,
            text=f"协作会话 {session_id} 已结束",
            score=1.0,
            data={"session_id": session_id, "status": status, "duration_seconds": duration_seconds},
        )

    def _analyze_collaboration(self, request: EvaluationSchema) -> DomainResponse:
        """分析实时协作数据分布"""
        session_id = self.get_payload_data(request, "session_id")

        with self._sessions_lock:
            session_exists = session_id and session_id in self.collaboration_sessions

        analysis = self._analyze_session(session_id) if session_exists else self._analyze_overall()

        return DomainResponse(
            is_valid=True,
            text="协作分析完成",
            score=analysis.get("overall_score", 0.5),
            data=analysis,
        )

    def _evaluate_collaboration(self, request: EvaluationSchema) -> DomainResponse:
        """【重构亮点】评估多Agent协作（纯函数无污染执行，完美防御高并发下的状态擦除）"""
        agents_data = self.get_payload_data(request, "agents", [])
        messages_data = self.get_payload_data(request, "messages", [])
        tasks_data = self.get_payload_data(request, "tasks", [])
        conflicts_data = self.get_payload_data(request, "conflicts", [])

        # 将请求包中的原始数据完全解析为局部强类型结构，不直接触碰全局运行时属性
        (
            parsed_agents,
            parsed_messages,
            parsed_tasks,
            parsed_conflicts,
        ) = self._parse_collaboration_data(agents_data, messages_data, tasks_data, conflicts_data)

        # 驱动纯函数式流水线完成数学解算
        analysis = self._analyze_overall(
            agents_map=parsed_agents,
            messages_list=parsed_messages,
            tasks_list=parsed_tasks,
            conflicts_list=parsed_conflicts,
        )

        return DomainResponse(
            is_valid=True,
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
        """纯解算辅助：将原始报文结构化映射为强类型Slots实例"""
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
        """核心指标：分析通信质量"""
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
        """核心指标：分析任务分配效率与延迟惩罚项"""
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
        pending_tasks = sum(
            1
            for t in tasks
            if t.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS)
        )

        completion_rate = completed_tasks / total_tasks
        failure_rate = failed_tasks / total_tasks

        completion_times = [
            (t.completed_at - t.assigned_at) * 1000
            for t in tasks
            if t.status == TaskStatus.COMPLETED and t.completed_at > 0 and t.assigned_at > 0
        ]
        avg_completion_time = (
            sum(completion_times) / len(completion_times) if completion_times else 0.0
        )

        time_score = (
            max(0.0, min(1.0, 1.0 - (avg_completion_time / 10000.0)))
            if avg_completion_time > 0
            else 1.0
        )
        task_efficiency_score = (
            completion_rate * 0.5 + (1.0 - failure_rate) * 0.3 + time_score * 0.2
        )

        agent_task_distribution: dict[str, dict[str, int]] = {}
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

    def _analyze_conflicts(self, conflicts: list[Conflict] | None = None) -> dict[str, Any]:
        """分析系统冲突全局情况"""
        if conflicts is None:
            with self._conflicts_lock:
                conflicts = list(self.conflicts)
        return self._analyze_conflicts_for_agents(conflicts, None)

    def _analyze_conflicts_for_agents(
        self, conflicts: list[Conflict] | None, agent_ids: list[str] | None
    ) -> dict[str, Any]:
        """分析指定拓扑范围内的 Agent 拓扑冲突率"""
        if conflicts is None:
            with self._conflicts_lock:
                conflicts = list(self.conflicts)

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

        conflict_penalty = min(1.0, total_conflicts / 10.0)
        conflict_resolution_score = resolution_rate * (1.0 - conflict_penalty * 0.5)

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
        """【函数式重构】基于变异系数(CV)计算群落负载均衡度"""
        if agents_map is None:
            with self._agents_lock:
                agents_map = dict(self.agents)
        if tasks_len is None:
            with self._tasks_lock:
                tasks_len = len(self.tasks)
        if messages_len is None:
            with self._messages_lock:
                messages_len = len(self.messages)

        if not agents_map:
            return {
                "active_agents": 0,
                "avg_tasks_per_agent": 0.0,
                "avg_messages_per_agent": 0.0,
                "agent_utilization_rate": 0.0,
                "collaboration_score": 0.5,
            }

        total_agents = len(agents_map)
        active_agents = sum(1 for a in agents_map.values() if a.status == "active")
        avg_tasks_per_agent = tasks_len / total_agents
        avg_messages_per_agent = messages_len / total_agents

        agents_with_tasks = sum(
            1 for a in agents_map.values() if a.completed_tasks > 0 or len(a.current_tasks) > 0
        )
        agent_utilization_rate = agents_with_tasks / total_agents
        activity_score = active_agents / total_agents

        # 基于精准变异系数 (CV = std_dev / mean) 计算负载均衡评分
        task_counts = [a.completed_tasks + len(a.current_tasks) for a in agents_map.values()]
        if task_counts and max(task_counts) > 0:
            avg_tasks = sum(task_counts) / len(task_counts)
            if avg_tasks > 0:
                variance = sum((t - avg_tasks) ** 2 for t in task_counts) / len(task_counts)
                std_dev = variance**0.5
                cv = std_dev / avg_tasks
                load_balance_score = max(0.0, 1.0 - cv)
            else:
                load_balance_score = 1.0
        else:
            load_balance_score = 1.0

        collaboration_score = (
            activity_score * 0.3 + agent_utilization_rate * 0.4 + load_balance_score * 0.3
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

    def _analyze_session(self, session_id: str) -> dict[str, Any]:
        """分析特定隔离会话的协同质量"""
        with self._sessions_lock:
            session = self.collaboration_sessions.get(session_id)
            if not session:
                return {"error": f"会话 {session_id} 不存在"}
            agent_ids = list(session["agent_ids"])

        with self._messages_lock:
            session_messages = [
                m for m in self.messages if m.sender_id in agent_ids or m.receiver_id in agent_ids
            ]
        with self._tasks_lock:
            session_tasks = [t for t in self.tasks.values() if t.agent_id in agent_ids]

        communication_analysis = self._analyze_communication(session_messages)
        task_analysis = self._analyze_tasks(session_tasks)

        with self._conflicts_lock:
            conflicts_snapshot = list(self.conflicts)
        conflict_analysis = self._analyze_conflicts_for_agents(conflicts_snapshot, agent_ids)

        with self._sessions_lock:
            session = self.collaboration_sessions.get(session_id)
            duration_seconds = (
                (session.get("end_time") or time.time()) - session["start_time"] if session else 0.0
            )

        overall_score = (
            communication_analysis.get("communication_score", 0.5) * 0.3
            + task_analysis.get("task_efficiency_score", 0.5) * 0.4
            + conflict_analysis.get("conflict_resolution_score", 0.5) * 0.3
        )

        return {
            "session_id": session_id,
            "communication": communication_analysis,
            "tasks": task_analysis,
            "conflicts": conflict_analysis,
            "overall_score": round(overall_score, 4),
            "duration_seconds": round(duration_seconds, 2),
        }

    def _analyze_overall(
        self,
        agents_map: dict[str, AgentInfo] | None = None,
        messages_list: list[AgentMessage] | None = None,
        tasks_list: list[AgentTask] | None = None,
        conflicts_list: list[Conflict] | None = None,
    ) -> dict[str, Any]:
        """核心解算大脑：全量管道指标聚合"""
        # 函数式降级捕获：若无外注参数（生产环境Live运行场景），主动获取内部状态锁快照
        if messages_list is None:
            with self._messages_lock:
                messages_list = list(self.messages)
        if tasks_list is None:
            with self._tasks_lock:
                tasks_list = list(self.tasks.values())
        if conflicts_list is None:
            with self._conflicts_lock:
                conflicts_list = list(self.conflicts)
        if agents_map is None:
            with self._agents_lock:
                agents_map = dict(self.agents)

        communication_analysis = self._analyze_communication(messages_list)
        task_analysis = self._analyze_tasks(tasks_list)
        conflict_analysis = self._analyze_conflicts_for_agents(conflicts_list, None)
        collaboration_analysis = self._analyze_collaboration_quality(
            agents_map, len(tasks_list), len(messages_list)
        )

        overall_score = (
            communication_analysis.get("communication_score", 0.5) * 0.25
            + task_analysis.get("task_efficiency_score", 0.5) * 0.35
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

    # 元数据访问接口

    def get_agent_info(self, agent_id: str) -> AgentInfo | None:
        """获取特定 Agent 信息"""
        with self._agents_lock:
            return self.agents.get(agent_id)

    def get_task_info(self, task_id: str) -> AgentTask | None:
        """获取特定任务信息"""
        with self._tasks_lock:
            return self.tasks.get(task_id)

    def get_conflict_info(self, conflict_id: str) -> Conflict | None:
        """获取特定冲突信息"""
        with self._conflicts_lock:
            for conflict in self.conflicts:
                if conflict.conflict_id == conflict_id:
                    return conflict
        return None

    def list_agents(self) -> list[str]:
        """列出所有已注册的 Agent ID"""
        with self._agents_lock:
            return list(self.agents.keys())

    def list_tasks(self) -> list[str]:
        """列出所有任务 ID"""
        with self._tasks_lock:
            return list(self.tasks.keys())

    def list_conflicts(self) -> list[str]:
        """列出所有冲突 ID"""
        with self._conflicts_lock:
            return [c.conflict_id for c in self.conflicts]

    def clear_data(self) -> None:
        """清空数据仓库"""
        with self._agents_lock:
            self.agents.clear()
        with self._messages_lock:
            self.messages.clear()
        with self._tasks_lock:
            self.tasks.clear()
        with self._conflicts_lock:
            self.conflicts.clear()
        with self._sessions_lock:
            self.collaboration_sessions.clear()
        logger.info("MultiAgentEvaluator 状态数据已完全重置清空")
