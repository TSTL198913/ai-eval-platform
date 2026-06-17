"""
安全认证模块集成测试
覆盖API密钥管理、权限检查、审计日志、请求签名
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.infra.security import (
    Permission,
    Role,
    ROLE_PERMISSIONS,
    APIKey,
    AuditLog,
    APIKeyManager,
    PermissionChecker,
    AuditLogger,
    RequestSigner,
    SecurityManager,
    get_security,
)


class TestPermission:
    """权限枚举测试"""

    def test_permission_values(self):
        """测试权限值"""
        assert Permission.EVALUATE.value == "evaluate"
        assert Permission.COMPARE.value == "compare"
        assert Permission.VIEW_REPORT.value == "view_report"
        assert Permission.MANAGE_MODELS.value == "manage_models"
        assert Permission.ADMIN.value == "admin"


class TestRole:
    """角色枚举测试"""

    def test_role_values(self):
        """测试角色值"""
        assert Role.GUEST.value == "guest"
        assert Role.USER.value == "user"
        assert Role.PREMIUM.value == "premium"
        assert Role.ENTERPRISE.value == "enterprise"
        assert Role.ADMIN.value == "admin"


class TestRolePermissions:
    """角色权限映射测试"""

    def test_guest_permissions(self):
        """测试访客权限"""
        assert Permission.VIEW_REPORT in ROLE_PERMISSIONS[Role.GUEST]
        assert Permission.EVALUATE not in ROLE_PERMISSIONS[Role.GUEST]

    def test_user_permissions(self):
        """测试用户权限"""
        permissions = ROLE_PERMISSIONS[Role.USER]
        assert Permission.EVALUATE in permissions
        assert Permission.VIEW_REPORT in permissions

    def test_admin_permissions(self):
        """测试管理员权限"""
        permissions = ROLE_PERMISSIONS[Role.ADMIN]
        assert len(permissions) == 5
        assert Permission.ADMIN in permissions


class TestAPIKey:
    """API密钥数据类测试"""

    def test_api_key_basic(self):
        """测试API密钥基本属性"""
        api_key = APIKey(
            key_id="key_001",
            key_hash="hash_value",
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )
        assert api_key.key_id == "key_001"
        assert api_key.user_id == "user_001"
        assert api_key.role == Role.USER
        assert api_key.is_active is True
        assert api_key.is_expired() is False

    def test_api_key_expired(self):
        """测试过期API密钥"""
        api_key = APIKey(
            key_id="key_001",
            key_hash="hash_value",
            user_id="user_001",
            role=Role.USER,
            name="test-key",
            expires_at=time.time() - 1000,
        )
        assert api_key.is_expired() is True

    def test_api_key_has_permission(self):
        """测试API密钥权限检查"""
        admin_key = APIKey(
            key_id="key_001",
            key_hash="hash_value",
            user_id="user_001",
            role=Role.ADMIN,
            name="admin-key",
        )
        user_key = APIKey(
            key_id="key_002",
            key_hash="hash_value",
            user_id="user_002",
            role=Role.USER,
            name="user-key",
        )

        assert admin_key.has_permission(Permission.ADMIN) is True
        assert user_key.has_permission(Permission.ADMIN) is False
        assert user_key.has_permission(Permission.EVALUATE) is True

    def test_api_key_to_dict(self):
        """测试API密钥转换为字典"""
        api_key = APIKey(
            key_id="key_001",
            key_hash="hash_value",
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )
        key_dict = api_key.to_dict()
        assert key_dict["key_id"] == "key_001"
        assert key_dict["user_id"] == "user_001"
        assert key_dict["role"] == "user"
        assert "key_hash" not in key_dict


class TestAPIKeyManager:
    """API密钥管理器集成测试"""

    def test_generate_key(self):
        """测试生成API密钥"""
        manager = APIKeyManager()
        key = manager.generate_key()
        assert key.startswith("ae_")
        assert len(key) == 35

    def test_create_key(self):
        """测试创建API密钥"""
        manager = APIKeyManager()
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        assert raw_key is not None
        assert api_key.key_id is not None
        assert api_key.user_id == "user_001"
        assert api_key.role == Role.USER
        assert api_key.name == "test-key"
        assert api_key.is_active is True

    def test_verify_key(self):
        """测试验证API密钥"""
        manager = APIKeyManager()
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        verified = manager.verify_key(raw_key)
        assert verified is not None
        assert verified.key_id == api_key.key_id

    def test_verify_invalid_key(self):
        """测试验证无效密钥"""
        manager = APIKeyManager()
        verified = manager.verify_key("invalid_key")
        assert verified is None

    def test_verify_inactive_key(self):
        """测试验证非活跃密钥"""
        manager = APIKeyManager()
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        api_key.is_active = False
        verified = manager.verify_key(raw_key)
        assert verified is None

    def test_revoke_key(self):
        """测试撤销API密钥"""
        manager = APIKeyManager()
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        result = manager.revoke_key(api_key.key_id)
        assert result is True
        assert api_key.is_active is False

    def test_delete_key(self):
        """测试删除API密钥"""
        manager = APIKeyManager()
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        result = manager.delete_key(api_key.key_id)
        assert result is True
        assert manager.get_key(api_key.key_id) is None

    def test_get_key(self):
        """测试获取API密钥"""
        manager = APIKeyManager()
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        fetched = manager.get_key(api_key.key_id)
        assert fetched is not None
        assert fetched.key_id == api_key.key_id

    def test_get_user_keys(self):
        """测试获取用户所有密钥"""
        manager = APIKeyManager()
        manager.create_key(user_id="user_001", role=Role.USER, name="key-1")
        manager.create_key(user_id="user_001", role=Role.USER, name="key-2")
        manager.create_key(user_id="user_002", role=Role.ADMIN, name="key-3")

        keys = manager.get_user_keys("user_001")
        assert len(keys) == 2

    def test_create_key_with_expiry(self):
        """测试创建带过期时间的密钥"""
        manager = APIKeyManager()
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.USER,
            name="temp-key",
            expires_days=1,
        )

        assert api_key.expires_at is not None
        assert api_key.expires_at > time.time()


class TestPermissionChecker:
    """权限检查器集成测试"""

    def test_check_permission_success(self):
        """测试权限检查成功"""
        manager = APIKeyManager()
        checker = PermissionChecker(manager)
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        has_permission, key = checker.check_permission(raw_key, Permission.EVALUATE)
        assert has_permission is True
        assert key is not None

    def test_check_permission_failure(self):
        """测试权限检查失败"""
        manager = APIKeyManager()
        checker = PermissionChecker(manager)
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.GUEST,
            name="guest-key",
        )

        has_permission, key = checker.check_permission(raw_key, Permission.EVALUATE)
        assert has_permission is False
        assert key is not None

    def test_check_role_success(self):
        """测试角色检查成功"""
        manager = APIKeyManager()
        checker = PermissionChecker(manager)
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.ADMIN,
            name="admin-key",
        )

        has_role, key = checker.check_role(raw_key, Role.USER)
        assert has_role is True

    def test_check_role_failure(self):
        """测试角色检查失败"""
        manager = APIKeyManager()
        checker = PermissionChecker(manager)
        raw_key, api_key = manager.create_key(
            user_id="user_001",
            role=Role.USER,
            name="user-key",
        )

        has_role, key = checker.check_role(raw_key, Role.ADMIN)
        assert has_role is False


class TestAuditLogger:
    """审计日志记录器集成测试"""

    def test_log_entry(self):
        """测试记录审计日志"""
        logger = AuditLogger()
        audit_log = logger.log(
            user_id="user_001",
            api_key_id="key_001",
            action="evaluate",
            resource="case_001",
            method="POST",
            path="/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            request_id="req_001",
            duration_ms=100.0,
        )

        assert audit_log.log_id is not None
        assert audit_log.user_id == "user_001"
        assert audit_log.action == "evaluate"
        assert audit_log.status_code == 200

    def test_get_user_logs(self):
        """测试获取用户日志"""
        logger = AuditLogger()
        logger.log(user_id="user_001", api_key_id="key_001", action="evaluate", resource="case_001", method="POST", path="/evaluate", status_code=200, ip_address="127.0.0.1", user_agent="test-agent", request_id="req_001", duration_ms=100.0)
        logger.log(user_id="user_001", api_key_id="key_001", action="view_report", resource="report_001", method="GET", path="/reports", status_code=200, ip_address="127.0.0.1", user_agent="test-agent", request_id="req_002", duration_ms=50.0)
        logger.log(user_id="user_002", api_key_id="key_002", action="evaluate", resource="case_002", method="POST", path="/evaluate", status_code=200, ip_address="127.0.0.1", user_agent="test-agent", request_id="req_003", duration_ms=150.0)

        logs = logger.get_user_logs("user_001")
        assert len(logs) == 2

    def test_get_recent_logs(self):
        """测试获取最近日志"""
        logger = AuditLogger()
        for i in range(5):
            logger.log(user_id="user_001", api_key_id="key_001", action="evaluate", resource=f"case_{i}", method="POST", path="/evaluate", status_code=200, ip_address="127.0.0.1", user_agent="test-agent", request_id=f"req_{i}", duration_ms=100.0)

        logs = logger.get_recent_logs(3)
        assert len(logs) == 3

    def test_search_logs(self):
        """测试搜索日志"""
        logger = AuditLogger()
        logger.log(user_id="user_001", api_key_id="key_001", action="evaluate", resource="case_001", method="POST", path="/evaluate", status_code=200, ip_address="127.0.0.1", user_agent="test-agent", request_id="req_001", duration_ms=100.0)
        logger.log(user_id="user_001", api_key_id="key_001", action="view_report", resource="report_001", method="GET", path="/reports", status_code=200, ip_address="127.0.0.1", user_agent="test-agent", request_id="req_002", duration_ms=50.0)

        results = logger.search_logs(user_id="user_001", action="evaluate")
        assert len(results) == 1
        assert results[0].action == "evaluate"

    def test_log_rotation(self):
        """测试日志轮转"""
        logger = AuditLogger(max_logs=3)
        for i in range(5):
            logger.log(user_id="user_001", api_key_id="key_001", action="evaluate", resource=f"case_{i}", method="POST", path="/evaluate", status_code=200, ip_address="127.0.0.1", user_agent="test-agent", request_id=f"req_{i}", duration_ms=100.0)

        assert len(logger._logs) == 3

    def test_get_stats(self):
        """测试获取统计"""
        logger = AuditLogger()
        logger.log(user_id="user_001", api_key_id="key_001", action="evaluate", resource="case_001", method="POST", path="/evaluate", status_code=200, ip_address="127.0.0.1", user_agent="test-agent", request_id="req_001", duration_ms=100.0)

        stats = logger.get_stats()
        assert stats["total_logs"] == 1
        assert stats["max_logs"] == 10000
        assert stats["users_with_logs"] == 1


class TestRequestSigner:
    """请求签名器集成测试"""

    def test_sign_request(self):
        """测试签名请求"""
        signer = RequestSigner("test-secret")
        signature = signer.sign_request(
            method="POST",
            path="/evaluate",
            timestamp=1234567890.0,
            body='{"test": "data"}',
        )

        assert signature is not None
        assert len(signature) == 64

    def test_verify_signature(self):
        """测试验证签名"""
        signer = RequestSigner("test-secret")
        timestamp = time.time()
        signature = signer.sign_request(
            method="POST",
            path="/evaluate",
            timestamp=timestamp,
            body='{"test": "data"}',
        )

        result = signer.verify_signature(
            method="POST",
            path="/evaluate",
            timestamp=timestamp,
            body='{"test": "data"}',
            signature=signature,
        )

        assert result is True

    def test_verify_invalid_signature(self):
        """测试验证无效签名"""
        signer = RequestSigner("test-secret")
        timestamp = time.time()

        result = signer.verify_signature(
            method="POST",
            path="/evaluate",
            timestamp=timestamp,
            body='{"test": "data"}',
            signature="invalid_signature",
        )

        assert result is False

    def test_verify_expired_signature(self):
        """测试验证过期签名"""
        signer = RequestSigner("test-secret")
        timestamp = time.time() - 400
        signature = signer.sign_request(
            method="POST",
            path="/evaluate",
            timestamp=timestamp,
            body='{"test": "data"}',
        )

        result = signer.verify_signature(
            method="POST",
            path="/evaluate",
            timestamp=timestamp,
            body='{"test": "data"}',
            signature=signature,
            max_age_seconds=300.0,
        )

        assert result is False


class TestSecurityManager:
    """安全管理器集成测试"""

    def test_create_api_key(self):
        """测试创建API密钥"""
        manager = SecurityManager("test-secret")
        raw_key, api_key = manager.create_api_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        assert raw_key is not None
        assert api_key is not None

    def test_verify_api_key(self):
        """测试验证API密钥"""
        manager = SecurityManager("test-secret")
        raw_key, api_key = manager.create_api_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        verified = manager.verify_api_key(raw_key)
        assert verified is not None

    def test_check_permission(self):
        """测试检查权限"""
        manager = SecurityManager("test-secret")
        raw_key, api_key = manager.create_api_key(
            user_id="user_001",
            role=Role.USER,
            name="test-key",
        )

        has_permission, key = manager.check_permission(raw_key, Permission.EVALUATE)
        assert has_permission is True

    def test_log_audit(self):
        """测试记录审计日志"""
        manager = SecurityManager("test-secret")
        audit_log = manager.log_audit(
            user_id="user_001",
            api_key_id="key_001",
            action="evaluate",
            resource="case_001",
            method="POST",
            path="/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            request_id="req_001",
            duration_ms=100.0,
        )

        assert audit_log is not None

    def test_sign_and_verify_request(self):
        """测试签名和验证请求"""
        manager = SecurityManager("test-secret")
        timestamp = time.time()
        signature = manager.sign_request(
            method="POST",
            path="/evaluate",
            timestamp=timestamp,
            body='{"test": "data"}',
        )

        result = manager.verify_signature(
            method="POST",
            path="/evaluate",
            timestamp=timestamp,
            body='{"test": "data"}',
            signature=signature,
        )

        assert result is True

    def test_get_audit_stats(self):
        """测试获取审计统计"""
        manager = SecurityManager("test-secret")
        stats = manager.get_audit_stats()
        assert stats is not None
        assert "total_logs" in stats


class TestGetSecurity:
    """全局安全管理器测试"""

    def test_get_security(self):
        """测试获取全局安全管理器"""
        security = get_security("test-secret")
        assert security is not None
        assert isinstance(security, SecurityManager)

    def test_get_security_with_env_var(self):
        """测试通过环境变量获取安全管理器"""
        with patch("os.getenv", return_value="env-secret"):
            security = get_security()
            assert security is not None