"""
安全认证模块

包含：
1. API 密钥管理
2. 权限控制（RBAC）
3. 审计日志
4. 请求签名验证
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Permission(Enum):
    """权限枚举"""

    EVALUATE = "evaluate"  # 评测权限
    COMPARE = "compare"  # 对比权限
    VIEW_REPORT = "view_report"  # 查看报告
    MANAGE_MODELS = "manage_models"  # 管理模型
    ADMIN = "admin"  # 管理员权限


class Role(Enum):
    """角色枚举"""

    GUEST = "guest"  # 访客
    USER = "user"  # 普通用户
    PREMIUM = "premium"  # 高级用户
    ENTERPRISE = "enterprise"  # 企业用户
    ADMIN = "admin"  # 管理员


# 角色权限映射
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.GUEST: [Permission.VIEW_REPORT],
    Role.USER: [Permission.EVALUATE, Permission.VIEW_REPORT],
    Role.PREMIUM: [Permission.EVALUATE, Permission.COMPARE, Permission.VIEW_REPORT],
    Role.ENTERPRISE: [
        Permission.EVALUATE,
        Permission.COMPARE,
        Permission.VIEW_REPORT,
        Permission.MANAGE_MODELS,
    ],
    Role.ADMIN: list(Permission),  # 所有权限
}


@dataclass
class APIKey:
    """API 密钥"""

    key_id: str
    key_hash: str  # 存储哈希值，不存储原始密钥
    user_id: str
    role: Role
    name: str
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    is_active: bool = True
    rate_limit: int = 100  # 每分钟请求限制
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def has_permission(self, permission: Permission) -> bool:
        """检查是否有权限"""
        return permission in ROLE_PERMISSIONS.get(self.role, [])

    def to_dict(self) -> dict:
        """转换为字典（不包含敏感信息）"""
        return {
            "key_id": self.key_id,
            "user_id": self.user_id,
            "role": self.role.value,
            "name": self.name,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "is_active": self.is_active,
            "rate_limit": self.rate_limit,
        }


@dataclass
class AuditLog:
    """审计日志"""

    log_id: str
    user_id: str
    api_key_id: str
    action: str
    resource: str
    method: str
    path: str
    status_code: int
    ip_address: str
    user_agent: str
    request_id: str
    duration_ms: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "api_key_id": self.api_key_id,
            "action": self.action,
            "resource": self.resource,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class APIKeyManager:
    """
    API 密钥管理器

    管理 API 密钥的创建、验证、撤销等操作。
    """

    def __init__(self):
        self._keys: dict[str, APIKey] = {}  # key_id -> APIKey
        self._key_hashes: dict[str, str] = {}  # key_hash -> key_id

    def generate_key(self, prefix: str = "ae") -> str:
        """生成 API 密钥"""
        import secrets

        random_part = secrets.token_hex(16)
        return f"{prefix}_{random_part}"

    def create_key(
        self,
        user_id: str,
        role: Role,
        name: str,
        expires_days: int | None = None,
        rate_limit: int = 100,
    ) -> tuple[str, APIKey]:
        """
        创建 API 密钥

        Returns:
            (raw_key, api_key_object)
        """
        import uuid

        key_id = str(uuid.uuid4())
        raw_key = self.generate_key()

        # 存储哈希值
        key_hash = self._hash_key(raw_key)

        expires_at = None
        if expires_days:
            expires_at = time.time() + expires_days * 86400

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            role=role,
            name=name,
            expires_at=expires_at,
            rate_limit=rate_limit,
        )

        self._keys[key_id] = api_key
        self._key_hashes[key_hash] = key_id

        logger.info(f"Created API key {key_id} for user {user_id} with role {role.value}")

        return raw_key, api_key

    def verify_key(self, raw_key: str) -> APIKey | None:
        """验证 API 密钥"""
        key_hash = self._hash_key(raw_key)
        key_id = self._key_hashes.get(key_hash)

        if not key_id:
            return None

        api_key = self._keys.get(key_id)
        if not api_key:
            return None

        # 检查状态
        if not api_key.is_active:
            logger.warning(f"API key {key_id} is inactive")
            return None

        # 检查过期
        if api_key.is_expired():
            logger.warning(f"API key {key_id} is expired")
            return None

        return api_key

    def revoke_key(self, key_id: str) -> bool:
        """撤销 API 密钥"""
        if key_id in self._keys:
            api_key = self._keys[key_id]
            api_key.is_active = False
            logger.info(f"Revoked API key {key_id}")
            return True
        return False

    def delete_key(self, key_id: str) -> bool:
        """删除 API 密钥"""
        if key_id in self._keys:
            api_key = self._keys[key_id]
            del self._keys[key_id]
            del self._key_hashes[api_key.key_hash]
            logger.info(f"Deleted API key {key_id}")
            return True
        return False

    def get_key(self, key_id: str) -> APIKey | None:
        """获取 API 密钥"""
        return self._keys.get(key_id)

    def get_user_keys(self, user_id: str) -> list[APIKey]:
        """获取用户的所有密钥"""
        return [k for k in self._keys.values() if k.user_id == user_id]

    def _hash_key(self, raw_key: str) -> str:
        """哈希密钥"""
        return hashlib.sha256(raw_key.encode()).hexdigest()


class PermissionChecker:
    """
    权限检查器

    基于 RBAC 检查用户权限。
    """

    def __init__(self, api_key_manager: APIKeyManager):
        self._key_manager = api_key_manager

    def check_permission(
        self, raw_key: str, permission: Permission, resource: str | None = None
    ) -> tuple[bool, APIKey | None]:
        """
        检查权限

        Returns:
            (has_permission, api_key)
        """
        api_key = self._key_manager.verify_key(raw_key)
        if not api_key:
            return False, None

        # 检查角色权限
        if not api_key.has_permission(permission):
            logger.warning(
                f"User {api_key.user_id} lacks permission {permission.value}"
            )
            return False, api_key

        return True, api_key

    def check_role(self, raw_key: str, required_role: Role) -> tuple[bool, APIKey | None]:
        """检查角色"""
        api_key = self._key_manager.verify_key(raw_key)
        if not api_key:
            return False, None

        # 检查角色级别
        role_levels = {
            Role.GUEST: 0,
            Role.USER: 1,
            Role.PREMIUM: 2,
            Role.ENTERPRISE: 3,
            Role.ADMIN: 4,
        }

        if role_levels.get(api_key.role, 0) < role_levels.get(required_role, 0):
            return False, api_key

        return True, api_key


class AuditLogger:
    """
    审计日志记录器

    记录所有 API 操作的审计日志。
    """

    def __init__(self, max_logs: int = 10000):
        self._logs: list[AuditLog] = []
        self._max_logs = max_logs
        self._log_index: dict[str, list[AuditLog]] = {}  # user_id -> logs

    def log(
        self,
        user_id: str,
        api_key_id: str,
        action: str,
        resource: str,
        method: str,
        path: str,
        status_code: int,
        ip_address: str,
        user_agent: str,
        request_id: str,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """记录审计日志"""
        import uuid

        log_id = str(uuid.uuid4())

        audit_log = AuditLog(
            log_id=log_id,
            user_id=user_id,
            api_key_id=api_key_id,
            action=action,
            resource=resource,
            method=method,
            path=path,
            status_code=status_code,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        # 添加到列表
        self._logs.append(audit_log)

        # 添加到用户索引
        if user_id not in self._log_index:
            self._log_index[user_id] = []
        self._log_index[user_id].append(audit_log)

        # 检查容量
        if len(self._logs) > self._max_logs:
            self._rotate_logs()

        logger.debug(f"Logged audit entry {log_id} for user {user_id}")
        return audit_log

    def get_user_logs(self, user_id: str, limit: int = 100) -> list[AuditLog]:
        """获取用户日志"""
        logs = self._log_index.get(user_id, [])
        return logs[-limit:]

    def get_recent_logs(self, limit: int = 100) -> list[AuditLog]:
        """获取最近日志"""
        return self._logs[-limit:]

    def search_logs(
        self,
        user_id: str | None = None,
        action: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> list[AuditLog]:
        """搜索日志"""
        results = []

        for log in self._logs:
            if user_id and log.user_id != user_id:
                continue
            if action and log.action != action:
                continue
            if start_time and log.timestamp < start_time:
                continue
            if end_time and log.timestamp > end_time:
                continue

            results.append(log)

        return results

    def _rotate_logs(self):
        """轮转日志"""
        # 删除最旧的日志
        removed = self._logs[: len(self._logs) - self._max_logs]
        self._logs = self._logs[len(self._logs) - self._max_logs :]

        # 更新索引
        for log in removed:
            if log.user_id in self._log_index:
                user_logs = self._log_index[log.user_id]
                if log in user_logs:
                    user_logs.remove(log)

        logger.info(f"Rotated {len(removed)} audit logs")

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "total_logs": len(self._logs),
            "max_logs": self._max_logs,
            "users_with_logs": len(self._log_index),
        }


class RequestSigner:
    """
    请求签名器

    用于验证请求的完整性。
    """

    def __init__(self, secret_key: str):
        self._secret_key = secret_key

    def sign_request(
        self, method: str, path: str, timestamp: float, body: str | None = None
    ) -> str:
        """签名请求"""
        message = f"{method}\n{path}\n{timestamp}\n{body or ''}"
        signature = hmac.new(
            self._secret_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def verify_signature(
        self,
        method: str,
        path: str,
        timestamp: float,
        body: str | None = None,
        signature: str | None = None,
        max_age_seconds: float = 300.0,
    ) -> bool:
        """验证签名"""
        if not signature:
            return False

        # 检查时间戳
        if time.time() - timestamp > max_age_seconds:
            logger.warning("Request signature expired")
            return False

        # 计算预期签名
        expected = self.sign_request(method, path, timestamp, body)

        # 比较
        return hmac.compare_digest(signature, expected)


class SecurityManager:
    """
    安全管理器

    综合管理 API 密钥、权限、审计日志等。
    """

    def __init__(self, secret_key: str):
        self._api_key_manager = APIKeyManager()
        self._permission_checker = PermissionChecker(self._api_key_manager)
        self._audit_logger = AuditLogger()
        self._request_signer = RequestSigner(secret_key)

    def create_api_key(self, **kwargs) -> tuple[str, APIKey]:
        """创建 API 密钥"""
        return self._api_key_manager.create_key(**kwargs)

    def verify_api_key(self, raw_key: str) -> APIKey | None:
        """验证 API 密钥"""
        return self._api_key_manager.verify_key(raw_key)

    def check_permission(self, raw_key: str, permission: Permission) -> tuple[bool, APIKey | None]:
        """检查权限"""
        return self._permission_checker.check_permission(raw_key, permission)

    def log_audit(self, **kwargs) -> AuditLog:
        """记录审计日志"""
        return self._audit_logger.log(**kwargs)

    def sign_request(self, **kwargs) -> str:
        """签名请求"""
        return self._request_signer.sign_request(**kwargs)

    def verify_signature(self, **kwargs) -> bool:
        """验证签名"""
        return self._request_signer.verify_signature(**kwargs)

    def get_audit_stats(self) -> dict:
        """获取审计统计"""
        return self._audit_logger.get_stats()


# 全局安全管理器
_global_security: SecurityManager | None = None


def get_security(secret_key: str | None = None) -> SecurityManager:
    """获取全局安全管理器"""
    if _global_security is None:
        import os

        secret = secret_key or os.getenv("AI_EVAL_SECRET_KEY", "default-secret-key")
        _global_security = SecurityManager(secret)
    return _global_security