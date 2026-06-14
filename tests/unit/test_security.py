"""测试 src/infra/security.py - 安全认证模块"""

from unittest.mock import Mock, patch

import pytest

from src.infra.security import (
    APIKey,
    APIKeyManager,
    AuditLog,
    AuditLogger,
    Permission,
    PermissionChecker,
    RequestSigner,
    Role,
    ROLE_PERMISSIONS,
    SecurityManager,
)


class TestRolePermissions:
    """测试角色权限映射"""

    def test_guest_permissions(self):
        """测试访客权限"""
        assert Permission.VIEW_REPORT in ROLE_PERMISSIONS[Role.GUEST]
        assert Permission.EVALUATE not in ROLE_PERMISSIONS[Role.GUEST]

    def test_user_permissions(self):
        """测试用户权限"""
        assert Permission.EVALUATE in ROLE_PERMISSIONS[Role.USER]
        assert Permission.VIEW_REPORT in ROLE_PERMISSIONS[Role.USER]
        assert Permission.COMPARE not in ROLE_PERMISSIONS[Role.USER]

    def test_admin_permissions(self):
        """测试管理员权限"""
        assert all(p in ROLE_PERMISSIONS[Role.ADMIN] for p in Permission)


class TestAPIKey:
    """测试 API 密钥"""

    def test_is_expired(self):
        """测试过期检查"""
        import time

        # 未过期
        key = APIKey(
            key_id="test",
            key_hash="hash",
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )
        assert key.is_expired() is False

        # 已过期
        key_expired = APIKey(
            key_id="test",
            key_hash="hash",
            user_id="user1",
            role=Role.USER,
            name="Test Key",
            expires_at=time.time() - 100,
        )
        assert key_expired.is_expired() is True

    def test_has_permission(self):
        """测试权限检查"""
        key = APIKey(
            key_id="test",
            key_hash="hash",
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )
        assert key.has_permission(Permission.EVALUATE) is True
        assert key.has_permission(Permission.ADMIN) is False

    def test_to_dict(self):
        """测试转换为字典"""
        key = APIKey(
            key_id="test",
            key_hash="hash",
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )
        data = key.to_dict()
        assert data["key_id"] == "test"
        assert data["user_id"] == "user1"
        assert data["role"] == "user"
        assert "key_hash" not in data  # 不应包含敏感信息


class TestAPIKeyManager:
    """测试 API 密钥管理器"""

    @pytest.fixture
    def manager(self):
        return APIKeyManager()

    def test_generate_key(self, manager):
        """测试生成密钥"""
        key = manager.generate_key()
        assert key.startswith("ae_")
        assert len(key) == 35  # "ae_" + 32 字符

    def test_create_key(self, manager):
        """测试创建密钥"""
        raw_key, api_key = manager.create_key(
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )
        assert raw_key.startswith("ae_")
        assert api_key.user_id == "user1"
        assert api_key.role == Role.USER

    def test_verify_key(self, manager):
        """测试验证密钥"""
        raw_key, api_key = manager.create_key(
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )

        verified = manager.verify_key(raw_key)
        assert verified is not None
        assert verified.key_id == api_key.key_id

    def test_verify_invalid_key(self, manager):
        """测试验证无效密钥"""
        result = manager.verify_key("invalid_key")
        assert result is None

    def test_revoke_key(self, manager):
        """测试撤销密钥"""
        _, api_key = manager.create_key(
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )

        revoked = manager.revoke_key(api_key.key_id)
        assert revoked is True
        assert api_key.is_active is False

    def test_delete_key(self, manager):
        """测试删除密钥"""
        _, api_key = manager.create_key(
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )

        deleted = manager.delete_key(api_key.key_id)
        assert deleted is True
        assert manager.get_key(api_key.key_id) is None

    def test_get_user_keys(self, manager):
        """测试获取用户密钥"""
        manager.create_key(user_id="user1", role=Role.USER, name="Key1")
        manager.create_key(user_id="user1", role=Role.PREMIUM, name="Key2")
        manager.create_key(user_id="user2", role=Role.USER, name="Key3")

        keys = manager.get_user_keys("user1")
        assert len(keys) == 2


class TestPermissionChecker:
    """测试权限检查器"""

    @pytest.fixture
    def checker(self):
        manager = APIKeyManager()
        return PermissionChecker(manager)

    def test_check_permission_success(self, checker):
        """测试权限检查成功"""
        raw_key, _ = checker._key_manager.create_key(
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )

        has_perm, api_key = checker.check_permission(raw_key, Permission.EVALUATE)
        assert has_perm is True
        assert api_key is not None

    def test_check_permission_denied(self, checker):
        """测试权限不足"""
        raw_key, _ = checker._key_manager.create_key(
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )

        has_perm, _ = checker.check_permission(raw_key, Permission.ADMIN)
        assert has_perm is False

    def test_check_role(self, checker):
        """测试角色检查"""
        raw_key, _ = checker._key_manager.create_key(
            user_id="user1",
            role=Role.PREMIUM,  # 使用存在的角色
            name="Test Key",
        )

        has_role, _ = checker.check_role(raw_key, Role.USER)
        assert has_role is True

        has_role, _ = checker.check_role(raw_key, Role.ENTERPRISE)
        assert has_role is False


class TestAuditLogger:
    """测试审计日志记录器"""

    @pytest.fixture
    def audit_logger(self):
        return AuditLogger(max_logs=100)

    def test_log(self, audit_logger):
        """测试记录日志"""
        log = audit_logger.log(
            user_id="user1",
            api_key_id="key1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/v1/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
        )

        assert log.log_id is not None
        assert log.user_id == "user1"
        assert log.status_code == 200

    def test_get_user_logs(self, audit_logger):
        """测试获取用户日志"""
        audit_logger.log(user_id="user1", api_key_id="key1", action="evaluate", resource="model", method="POST", path="/v1/evaluate", status_code=200, ip_address="127.0.0.1", user_agent="test", request_id="req1", duration_ms=100.0)
        audit_logger.log(user_id="user1", api_key_id="key1", action="compare", resource="model", method="POST", path="/v1/compare", status_code=200, ip_address="127.0.0.1", user_agent="test", request_id="req2", duration_ms=100.0)

        logs = audit_logger.get_user_logs("user1")
        assert len(logs) == 2

    def test_search_logs(self, audit_logger):
        """测试搜索日志"""
        audit_logger.log(user_id="user1", api_key_id="key1", action="evaluate", resource="model", method="POST", path="/v1/evaluate", status_code=200, ip_address="127.0.0.1", user_agent="test", request_id="req1", duration_ms=100.0)
        audit_logger.log(user_id="user1", api_key_id="key1", action="compare", resource="model", method="POST", path="/v1/compare", status_code=200, ip_address="127.0.0.1", user_agent="test", request_id="req2", duration_ms=100.0)

        logs = audit_logger.search_logs(action="evaluate")
        assert len(logs) == 1
        assert logs[0].action == "evaluate"

    def test_get_stats(self, audit_logger):
        """测试获取统计"""
        audit_logger.log(user_id="user1", api_key_id="key1", action="evaluate", resource="model", method="POST", path="/v1/evaluate", status_code=200, ip_address="127.0.0.1", user_agent="test", request_id="req1", duration_ms=100.0)

        stats = audit_logger.get_stats()
        assert stats["total_logs"] == 1
        assert stats["max_logs"] == 100


class TestRequestSigner:
    """测试请求签名器"""

    @pytest.fixture
    def signer(self):
        return RequestSigner("test-secret-key")

    def test_sign_request(self, signer):
        """测试签名请求"""
        signature = signer.sign_request(
            method="POST",
            path="/v1/evaluate",
            timestamp=1234567890.0,
            body='{"model":"gpt-4"}',
        )
        assert len(signature) == 64  # SHA256 hex

    def test_verify_signature_success(self, signer):
        """测试验证签名成功"""
        import time

        timestamp = time.time()
        signature = signer.sign_request(
            method="POST",
            path="/v1/evaluate",
            timestamp=timestamp,
        )

        is_valid = signer.verify_signature(
            method="POST",
            path="/v1/evaluate",
            timestamp=timestamp,
            signature=signature,
        )
        assert is_valid is True

    def test_verify_signature_expired(self, signer):
        """测试验证过期签名"""
        import time

        old_timestamp = time.time() - 400  # 超过 5 分钟
        signature = signer.sign_request(
            method="POST",
            path="/v1/evaluate",
            timestamp=old_timestamp,
        )

        is_valid = signer.verify_signature(
            method="POST",
            path="/v1/evaluate",
            timestamp=old_timestamp,
            signature=signature,
            max_age_seconds=300.0,
        )
        assert is_valid is False

    def test_verify_signature_invalid(self, signer):
        """测试验证无效签名"""
        import time

        is_valid = signer.verify_signature(
            method="POST",
            path="/v1/evaluate",
            timestamp=time.time(),
            signature="invalid-signature",
        )
        assert is_valid is False


class TestSecurityManager:
    """测试安全管理器"""

    @pytest.fixture
    def security(self):
        return SecurityManager("test-secret-key")

    def test_create_api_key(self, security):
        """测试创建 API 密钥"""
        raw_key, api_key = security.create_api_key(
            user_id="user1",
            role=Role.ENTERPRISE,
            name="Enterprise Key",
        )
        assert raw_key is not None
        assert api_key.role == Role.ENTERPRISE

    def test_verify_api_key(self, security):
        """测试验证 API 密钥"""
        raw_key, _ = security.create_api_key(
            user_id="user1",
            role=Role.USER,
            name="Test Key",
        )

        api_key = security.verify_api_key(raw_key)
        assert api_key is not None

    def test_check_permission(self, security):
        """测试权限检查"""
        raw_key, _ = security.create_api_key(
            user_id="user1",
            role=Role.PREMIUM,
            name="Premium Key",
        )

        has_perm, _ = security.check_permission(raw_key, Permission.COMPARE)
        assert has_perm is True

    def test_log_audit(self, security):
        """测试记录审计日志"""
        log = security.log_audit(
            user_id="user1",
            api_key_id="key1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/v1/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
        )
        assert log.log_id is not None

    def test_sign_and_verify(self, security):
        """测试签名和验证"""
        import time

        timestamp = time.time()
        signature = security.sign_request(
            method="POST",
            path="/v1/evaluate",
            timestamp=timestamp,
        )

        is_valid = security.verify_signature(
            method="POST",
            path="/v1/evaluate",
            timestamp=timestamp,
            signature=signature,
        )
        assert is_valid is True
