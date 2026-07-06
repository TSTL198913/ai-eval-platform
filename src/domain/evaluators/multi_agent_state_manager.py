"""MultiAgent 状态管理器 - 独立的状态管理模块

用于管理多Agent系统中的状态数据，包括：
- Agent注册与信息管理
- 消息记录与追踪
- 任务分配与状态更新
- 冲突检测与解决
- 协作会话管理

遵循单一职责原则，将状态管理与评估逻辑分离。
"""

import json
import logging
import re
import threading
import time
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_HTML_RE = re.compile(r"<[^>]+>")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_input(text: str, max_length: int = 1000) -> str:
    if not text:
        return ""
    text = text[:max_length]
    text = _SCRIPT_RE.sub("", text)
    text = _HTML_RE.sub("", text)
    text = _CONTROL_CHAR_RE.sub("", text)
    return text.strip()


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    NOTIFICATION = "notification"
    ERROR = "error"


class ConflictType(str, Enum):
    RESOURCE = "resource"
    TASK = "task"
    COMMUNICATION = "communication"
    PRIORITY = "priority"
    DATA = "data"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class AgentMessage:
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
    conflict_id: str
    conflict_type: ConflictType
    agent_ids: list[str]
    description: str
    timestamp: float
    resolved: bool = False
    resolution: str | None = None


@dataclass(slots=True)
class AgentInfo:
    agent_id: str
    role: str
    capabilities: list[str] = field(default_factory=list)
    status: str = "active"
    current_tasks: list[str] = field(default_factory=list)
    message_count: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0


class MultiAgentStateManager:
    """多Agent状态管理器 - 独立的状态管理模块"""

    def __init__(self, redis_client=None):
        self._agents_lock = threading.Lock()
        self._messages_lock = threading.Lock()
        self._tasks_lock = threading.Lock()
        self._conflicts_lock = threading.Lock()
        self._sessions_lock = threading.Lock()
        self._redis_client = redis_client
        self._persistence_key = "multi_agent_state"

        self.agents: dict[str, AgentInfo] = {}
        self.messages: list[AgentMessage] = []
        self.tasks: dict[str, AgentTask] = {}
        self.conflicts: list[Conflict] = []
        self.collaboration_sessions: dict[str, dict[str, Any]] = {}

        self._load_snapshot()

    def register_agent(self, agent_id: str, role: str = "worker", capabilities: list[str] = None) -> bool:
        if not agent_id:
            return False
        agent = AgentInfo(agent_id=agent_id, role=role, capabilities=capabilities or [])
        with self._agents_lock:
            self.agents[agent_id] = agent
        self._save_snapshot()
        return True

    def record_message(
        self,
        sender_id: str,
        receiver_id: str,
        content: str,
        message_type: str = "request",
        message_id: str = None,
        latency_ms: float = 0.0,
        is_delivered: bool = True,
        is_acknowledged: bool = False,
        metadata: dict = None,
    ) -> str | None:
        if not sender_id or not receiver_id:
            return None
        try:
            msg_type = MessageType(message_type)
        except ValueError:
            return None

        with self._messages_lock:
            msg_id = message_id or f"msg-{len(self.messages)}"
            message = AgentMessage(
                message_id=msg_id,
                sender_id=sender_id,
                receiver_id=receiver_id,
                message_type=msg_type,
                content=sanitize_input(content),
                timestamp=time.time(),
                latency_ms=latency_ms,
                is_delivered=is_delivered,
                is_acknowledged=is_acknowledged,
                metadata=metadata or {},
            )
            self.messages.append(message)

        with self._agents_lock:
            if sender_id in self.agents:
                self.agents[sender_id].message_count += 1

        self._save_snapshot()
        return msg_id

    def assign_task(
        self,
        task_id: str,
        agent_id: str,
        description: str = "",
        priority: int = 1,
        dependencies: list[str] = None,
    ) -> bool:
        if not task_id or not agent_id:
            return False

        with self._agents_lock:
            if agent_id not in self.agents:
                return False

        task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            description=sanitize_input(description),
            status=TaskStatus.ASSIGNED,
            priority=priority,
            assigned_at=time.time(),
            dependencies=dependencies or [],
        )

        with self._tasks_lock:
            self.tasks[task_id] = task
        with self._agents_lock:
            self.agents[agent_id].current_tasks.append(task_id)

        self._save_snapshot()
        return True

    def update_task(
        self,
        task_id: str,
        status: str,
        result: Any = None,
        error: str = "",
    ) -> bool:
        try:
            new_status = TaskStatus(status)
        except ValueError:
            return False

        agent_id = None
        task_info = None

        with self._tasks_lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            task.status = new_status

            if task.status == TaskStatus.COMPLETED:
                task.completed_at = time.time()
                task.result = result
                agent_id = task.agent_id
                task_info = {"task_id": task_id, "status": new_status}
            elif task.status == TaskStatus.FAILED:
                task.error = sanitize_input(error)
                agent_id = task.agent_id
                task_info = {"task_id": task_id, "status": new_status}
            else:
                agent_id = None

        if agent_id and task_info:
            with self._agents_lock:
                if agent_id in self.agents:
                    agent_info = self.agents[agent_id]
                    if task_info["status"] == TaskStatus.COMPLETED:
                        agent_info.completed_tasks += 1
                    elif task_info["status"] == TaskStatus.FAILED:
                        agent_info.failed_tasks += 1
                    if task_info["task_id"] in agent_info.current_tasks:
                        agent_info.current_tasks.remove(task_info["task_id"])

        self._save_snapshot()
        return True

    def record_conflict(
        self,
        conflict_type: str,
        agent_ids: list[str],
        description: str = "",
        conflict_id: str = None,
    ) -> str | None:
        if not agent_ids:
            return None

        try:
            conflict_type_enum = ConflictType(conflict_type)
        except ValueError:
            return None

        with self._conflicts_lock:
            c_id = conflict_id or f"conflict-{len(self.conflicts)}"
            conflict = Conflict(
                conflict_id=c_id,
                conflict_type=conflict_type_enum,
                agent_ids=agent_ids,
                description=sanitize_input(description),
                timestamp=time.time(),
            )
            self.conflicts.append(conflict)

        self._save_snapshot()
        return c_id

    def resolve_conflict(self, conflict_id: str, resolution: str = "") -> bool:
        with self._conflicts_lock:
            for conflict in self.conflicts:
                if conflict.conflict_id == conflict_id:
                    conflict.resolved = True
                    conflict.resolution = sanitize_input(resolution)
                    self._save_snapshot()
                    return True
        return False

    def start_session(self, session_id: str, agent_ids: list[str] = None, goal: str = "") -> bool:
        if not session_id:
            return False
        with self._sessions_lock:
            self.collaboration_sessions[session_id] = {
                "session_id": session_id,
                "agent_ids": agent_ids or [],
                "goal": goal,
                "start_time": time.time(),
                "end_time": None,
                "status": "active",
            }
        self._save_snapshot()
        return True

    def end_session(self, session_id: str, status: str = "completed") -> float | None:
        duration = None
        with self._sessions_lock:
            if session_id not in self.collaboration_sessions:
                return None

            session = self.collaboration_sessions[session_id]
            session["end_time"] = time.time()
            session["status"] = status
            duration = session["end_time"] - session["start_time"]
        self._save_snapshot()
        return duration

    def get_session_info(self, session_id: str) -> dict | None:
        with self._sessions_lock:
            return self.collaboration_sessions.get(session_id)

    def get_agent_info(self, agent_id: str) -> AgentInfo | None:
        with self._agents_lock:
            return self.agents.get(agent_id)

    def get_task_info(self, task_id: str) -> AgentTask | None:
        with self._tasks_lock:
            return self.tasks.get(task_id)

    def get_conflict_info(self, conflict_id: str) -> Conflict | None:
        with self._conflicts_lock:
            for conflict in self.conflicts:
                if conflict.conflict_id == conflict_id:
                    return conflict
        return None

    def list_agents(self) -> list[str]:
        with self._agents_lock:
            return list(self.agents.keys())

    def list_tasks(self) -> list[str]:
        with self._tasks_lock:
            return list(self.tasks.keys())

    def list_conflicts(self) -> list[str]:
        with self._conflicts_lock:
            return [c.conflict_id for c in self.conflicts]

    def get_snapshot(self) -> tuple[dict, list, list, list]:
        with self._agents_lock:
            agents = dict(self.agents)
        with self._messages_lock:
            messages = list(self.messages)
        with self._tasks_lock:
            tasks = list(self.tasks.values())
        with self._conflicts_lock:
            conflicts = list(self.conflicts)
        return agents, messages, tasks, conflicts

    def clear_data(self) -> None:
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
        self._save_snapshot()
        logger.info("MultiAgentStateManager 状态数据已完全重置清空")

    def _save_snapshot(self):
        if not self._redis_client:
            return
        try:
            snapshot = {
                "agents": {k: asdict(v) for k, v in self.agents.items()},
                "messages": [asdict(m) for m in self.messages],
                "tasks": {k: asdict(v) for k, v in self.tasks.items()},
                "conflicts": [asdict(c) for c in self.conflicts],
                "sessions": self.collaboration_sessions,
            }
            self._redis_client.set(self._persistence_key, json.dumps(snapshot))
        except Exception as e:
            logger.warning(f"保存状态快照失败: {e}")

    def _load_snapshot(self):
        if not self._redis_client:
            return
        try:
            snapshot_str = self._redis_client.get(self._persistence_key)
            if snapshot_str:
                snapshot = json.loads(snapshot_str)
                if "agents" in snapshot:
                    for k, v in snapshot["agents"].items():
                        self.agents[k] = AgentInfo(**v)
                if "messages" in snapshot:
                    for m in snapshot["messages"]:
                        m["message_type"] = MessageType(m["message_type"])
                        self.messages.append(AgentMessage(**m))
                if "tasks" in snapshot:
                    for k, v in snapshot["tasks"].items():
                        v["status"] = TaskStatus(v["status"])
                        self.tasks[k] = AgentTask(**v)
                if "conflicts" in snapshot:
                    for c in snapshot["conflicts"]:
                        c["conflict_type"] = ConflictType(c["conflict_type"])
                        self.conflicts.append(Conflict(**c))
                if "sessions" in snapshot:
                    self.collaboration_sessions = snapshot["sessions"]
                logger.info("状态快照加载成功")
        except Exception as e:
            logger.warning(f"加载状态快照失败: {e}")