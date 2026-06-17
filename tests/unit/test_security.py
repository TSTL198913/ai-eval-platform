import time
from unittest.mock import patch

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
    SecurityManager,
    get_security,
)


class TestPermissionAndRole:
    """权限和角色测试"""

    def test_role_permissions(self):
        """测试角色权限映射"""
        from src.infra.security import ROLE_PERMISSIONS

        assert Permission.ADMIN in ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.EVALUATE in ROLE_PERMISSIONS[Role.USER]
        assert Permission.VIEW_REPORT in ROLE_PERMISSIONS[Role.GUEST]


class TestAPIKey:
    """API密钥测试"""

    def test_is_expired_none(self):
        """测试无过期时间"""
        key = APIKey(
            key_id="k1",
            key_hash="hash",
            user_id="u1",
            role=Role.USER,
            name="test",
            expires_at=None,
        )
        assert key.is_expired() is False

    def test_is_expired_true(self):
        """测试已过期"""
        key = APIKey(
            key_id="k1",
            key_hash="hash",
            user_id="u1",
            role=Role.USER,
            name="test",
            expires_at=time.time() - 100,
        )
        assert key.is_expired() is True

    def test_is_expired_false(self):
        """测试未过期"""
        key = APIKey(
            key_id="k1",
            key_hash="hash",
            user_id="u1",
            role=Role.USER,
            name="test",
            expires_at=time.time() + 100,
        )
        assert key.is_expired() is False

    def test_has_permission(self):
        """测试权限检查"""
        key = APIKey(
            key_id="k1",
            key_hash="hash",
            user_id="u1",
            role=Role.ADMIN,
            name="test",
        )
        assert key.has_permission(Permission.ADMIN) is True
        assert key.has_permission(Permission.EVALUATE) is True

    def test_has_permission_guest(self):
        """测试访客权限"""
        key = APIKey(
            key_id="k1",
            key_hash="hash",
            user_id="u1",
            role=Role.GUEST,
            name="test",
        )
        assert key.has_permission(Permission.VIEW_REPORT) is True
        assert key.has_permission(Permission.EVALUATE) is False

    def test_to_dict(self):
        """测试转换为字典"""
        key = APIKey(
            key_id="k1",
            key_hash="hash",
            user_id="u1",
            role=Role.USER,
            name="test",
        )
        d = key.to_dict()

        assert d["key_id"] == "k1"
        assert d["role"] == "user"
        assert "key_hash" not in d


class TestAPIKeyManager:
    """API密钥管理器测试"""

    def setup_method(self):
        self.manager = APIKeyManager()

    def test_generate_key(self):
        """测试生成密钥"""
        key = self.manager.generate_key()
        assert key.startswith("ae_")
        assert len(key) > 20

    def test_generate_key_custom_prefix(self):
        """测试自定义前缀"""
        key = self.manager.generate_key(prefix="test")
        assert key.startswith("test_")

    def test_create_key(self):
        """测试创建密钥"""
        raw_key, api_key = self.manager.create_key(
            user_id="u1",
            role=Role.USER,
            name="test_key",
        )

        assert raw_key is not None
        assert api_key.user_id == "u1"
        assert api_key.role == Role.USER
        assert api_key.is_active is True

    def test_create_key_with_expiration(self):
        """测试创建有过期时间的密钥"""
        raw_key, api_key = self.manager.create_key(
            user_id="u1",
            role=Role.USER,
            name="test_key",
            expires_days=7,
        )

        assert api_key.expires_at is not None
        assert api_key.expires_at > time.time()

    def test_verify_key_success(self):
        """测试验证密钥成功"""
        raw_key, api_key = self.manager.create_key(
            user_id="u1",
            role=Role.USER,
            name="test_key",
        )

        verified = self.manager.verify_key(raw_key)
        assert verified is not None
        assert verified.key_id == api_key.key_id

    def test_verify_key_invalid(self):
        """测试验证无效密钥"""
        verified = self.manager.verify_key("invalid_key")
        assert verified is None

    def test_verify_key_inactive(self):
        """测试验证已撤销密钥"""
        raw_key, api_key = self.manager.create_key(
            user_id="u1",
            role=Role.USER,
            name="test_key",
        )
        api_key.is_active = False

        verified = self.manager.verify_key(raw_key)
        assert verified is None

    def test_verify_key_expired(self):
        """测试验证过期密钥"""
        raw_key, api_key = self.manager.create_key(
            user_id="u1",
            role=Role.USER,
            name="test_key",
            expires_days=-1,
        )

        verified = self.manager.verify_key(raw_key)
        assert verified is None

    def test_revoke_key(self):
        """测试撤销密钥"""
        raw_key, api_key = self.manager.create_key(
            user_id="u1",
            role=Role.USER,
            name="test_key",
        )

        result = self.manager.revoke_key(api_key.key_id)
        assert result is True
        assert api_key.is_active is False

    def test_revoke_key_not_found(self):
        """测试撤销不存在的密钥"""
        result = self.manager.revoke_key("nonexistent")
        assert result is False

    def test_delete_key(self):
        """测试删除密钥"""
        raw_key, api_key = self.manager.create_key(
            user_id="u1",
            role=Role.USER,
            name="test_key",
        )

        result = self.manager.delete_key(api_key.key_id)
        assert result is True
        assert api_key.key_id not in self.manager._keys

    def test_delete_key_not_found(self):
        """测试删除不存在的密钥"""
        result = self.manager.delete_key("nonexistent")
        assert result is False

    def test_get_key(self):
        """测试获取密钥"""
        raw_key, api_key = self.manager.create_key(
            user_id="u1",
            role=Role.USER,
            name="test_key",
        )

        found = self.manager.get_key(api_key.key_id)
        assert found is not None

    def test_get_user_keys(self):
        """测试获取用户密钥列表"""
        self.manager.create_key(user_id="u1", role=Role.USER, name="key1")
        self.manager.create_key(user_id="u1", role=Role.USER, name="key2")
        self.manager.create_key(user_id="u2", role=Role.USER, name="key3")

        keys = self.manager.get_user_keys("u1")
        assert len(keys) == 2


class TestPermissionChecker:
    """权限检查器测试"""

    def setup_method(self):
        self.key_manager = APIKeyManager()
        self.checker = PermissionChecker(self.key_manager)

    def test_check_permission_success(self):
        """测试权限检查通过"""
        raw_key, _ = self.key_manager.create_key(
            user_id="u1",
            role=Role.ADMIN,
            name="test_key",
        )

        has_perm, api_key = self.checker.check_permission(raw_key, Permission.ADMIN)
        assert has_perm is True
        assert api_key is not None

    def test_check_permission_denied(self):
        """测试权限检查拒绝"""
        raw_key, _ = self.key_manager.create_key(
            user_id="u1",
            role=Role.GUEST,
            name="test_key",
        )

        has_perm, api_key = self.checker.check_permission(raw_key, Permission.EVALUATE)
        assert has_perm is False
        assert api_key is not None

    def test_check_permission_invalid_key(self):
        """测试无效密钥"""
        has_perm, api_key = self.checker.check_permission("invalid", Permission.EVALUATE)
        assert has_perm is False
        assert api_key is None

    def test_check_role_sufficient(self):
        """测试角色足够"""
        raw_key, _ = self.key_manager.create_key(
            user_id="u1",
            role=Role.ADMIN,
            name="test_key",
        )

        has_role, api_key = self.checker.check_role(raw_key, Role.USER)
        assert has_role is True

    def test_check_role_insufficient(self):
        """测试角色不足"""
        raw_key, _ = self.key_manager.create_key(
            user_id="u1",
            role=Role.USER,
            name="test_key",
        )

        has_role, api_key = self.checker.check_role(raw_key, Role.ADMIN)
        assert has_role is False

    def test_check_role_invalid_key(self):
        """测试无效密钥检查角色"""
        has_role, api_key = self.checker.check_role("invalid", Role.USER)
        assert has_role is False
        assert api_key is None


class TestAuditLogger:
    """审计日志测试"""

    def setup_method(self):
        self.logger = AuditLogger(max_logs=5)

    def test_log(self):
        """测试记录日志"""
        log = self.logger.log(
            user_id="u1",
            api_key_id="k1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/api/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
        )

        assert log.user_id == "u1"
        assert log.action == "evaluate"

    def test_log_with_metadata(self):
        """测试带元数据的日志"""
        log = self.logger.log(
            user_id="u1",
            api_key_id="k1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/api/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
            metadata={"extra": "data"},
        )

        assert log.metadata == {"extra": "data"}

    def test_log_rotation(self):
        """测试日志轮转"""
        for i in range(7):
            self.logger.log(
                user_id="u1",
                api_key_id="k1",
                action=f"action_{i}",
                resource="model",
                method="POST",
                path="/api/evaluate",
                status_code=200,
                ip_address="127.0.0.1",
                user_agent="test",
                request_id=f"req{i}",
                duration_ms=100.0,
            )

        assert len(self.logger._logs) == 5

    def test_get_user_logs(self):
        """测试获取用户日志"""
        self.logger.log(
            user_id="u1",
            api_key_id="k1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/api/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
        )

        logs = self.logger.get_user_logs("u1")
        assert len(logs) == 1

    def test_get_recent_logs(self):
        """测试获取最近日志"""
        self.logger.log(
            user_id="u1",
            api_key_id="k1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/api/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
        )

        logs = self.logger.get_recent_logs(limit=10)
        assert len(logs) == 1

    def test_search_logs(self):
        """测试搜索日志"""
        self.logger.log(
            user_id="u1",
            api_key_id="k1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/api/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
        )

        results = self.logger.search_logs(user_id="u1", action="evaluate")
        assert len(results) == 1

        results = self.logger.search_logs(user_id="u2")
        assert len(results) == 0

        results = self.logger.search_logs(action="other")
        assert len(results) == 0

    def test_search_logs_by_time(self):
        """测试按时间搜索日志"""
        self.logger.log(
            user_id="u1",
            api_key_id="k1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/api/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
        )

        now = time.time()
        results = self.logger.search_logs(start_time=now + 10)
        assert len(results) == 0

        results = self.logger.search_logs(end_time=now - 10)
        assert len(results) == 0

    def test_get_stats(self):
        """测试获取统计"""
        self.logger.log(
            user_id="u1",
            api_key_id="k1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/api/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
        )

        stats = self.logger.get_stats()
        assert stats["total_logs"] == 1
        assert stats["users_with_logs"] == 1


class TestRequestSigner:
    """请求签名器测试"""

    def setup_method(self):
        self.signer = RequestSigner("secret_key")

    def test_sign_request(self):
        """测试签名请求"""
        signature = self.signer.sign_request("GET", "/api/test", 1234567890)

        assert len(signature) == 64
        assert signature != ""

    def test_sign_request_with_body(self):
        """测试带body的签名"""
        sig1 = self.signer.sign_request("GET", "/api/test", 1234567890)
        sig2 = self.signer.sign_request("GET", "/api/test", 1234567890, body="data")

        assert sig1 != sig2

    def test_verify_signature_success(self):
        """测试验证签名成功"""
        signature = self.signer.sign_request("GET", "/api/test", time.time())

        result = self.signer.verify_signature(
            "GET", "/api/test", time.time(), signature=signature
        )
        assert result is True

    def test_verify_signature_no_signature(self):
        """测试无签名"""
        result = self.signer.verify_signature("GET", "/api/test", time.time())
        assert result is False

    def test_verify_signature_expired(self):
        """测试签名过期"""
        old_time = time.time() - 400
        signature = self.signer.sign_request("GET", "/api/test", old_time)

        result = self.signer.verify_signature(
            "GET", "/api/test", old_time, signature=signature, max_age_seconds=300
        )
        assert result is False


class TestSecurityManager:
    """安全管理器测试"""

    def setup_method(self):
        self.security = SecurityManager("test_secret")

    def test_create_api_key(self):
        """测试创建API密钥"""
        raw_key, api_key = self.security.create_api_key(
            user_id="u1",
            role=Role.USER,
            name="test",
        )

        assert raw_key is not None
        assert api_key.user_id == "u1"

    def test_verify_api_key(self):
        """测试验证API密钥"""
        raw_key, _ = self.security.create_api_key(
            user_id="u1",
            role=Role.USER,
            name="test",
        )

        verified = self.security.verify_api_key(raw_key)
        assert verified is not None

    def test_check_permission(self):
        """测试检查权限"""
        raw_key, _ = self.security.create_api_key(
            user_id="u1",
            role=Role.ADMIN,
            name="test",
        )

        has_perm, api_key = self.security.check_permission(raw_key, Permission.ADMIN)
        assert has_perm is True

    def test_log_audit(self):
        """测试记录审计日志"""
        log = self.security.log_audit(
            user_id="u1",
            api_key_id="k1",
            action="evaluate",
            resource="model",
            method="POST",
            path="/api/evaluate",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="test",
            request_id="req1",
            duration_ms=100.0,
        )

        assert log.user_id == "u1"

    def test_sign_request(self):
        """测试签名请求"""
        signature = self.security.sign_request(
            method="GET", path="/api/test", timestamp=time.time()
        )

        assert len(signature) == 64

    def test_verify_signature(self):
        """测试验证签名"""
        ts = time.time()
        signature = self.security.sign_request(method="GET", path="/api/test", timestamp=ts)

        result = self.security.verify_signature(
            method="GET", path="/api/test", timestamp=ts, signature=signature
        )

        assert result is True

    def test_get_audit_stats(self):
        """测试获取审计统计"""
        stats = self.security.get_audit_stats()

        assert "total_logs" in stats
        assert "max_logs" in stats


class TestGetSecurity:
    """全局安全管理器测试"""

    def test_get_security_singleton(self):
        """测试单例模式"""
        sec1 = get_security("test_secret")
        sec2 = get_security("test_secret")

        assert sec1 is sec2

    def test_get_security_from_env(self):
        """测试从环境变量获取密钥"""
        with patch.dict("os.environ", {"AI_EVAL_SECRET_KEY": "env_secret"}):
            sec = get_security()
            assert sec is not None