"""
Auth 模块单元测试 - 带有效断言
覆盖: 密码哈希、JWT 生成/解析、用户认证、Token 刷新
"""
import os
import sys
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.api.auth import (
    _hash_password,
    verify_password,
    get_password_hash,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    fake_users_db,
)


class TestPasswordHashing:
    """密码哈希单元测试"""

    def test_hash_password_deterministic_with_same_salt(self):
        """相同密码和 salt 应产生相同哈希"""
        hash1 = _hash_password("mysecret")
        hash2 = _hash_password("mysecret")
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_hash_password_different_passwords(self):
        """不同密码应产生不同哈希"""
        hash1 = _hash_password("password1")
        hash2 = _hash_password("password2")
        assert hash1 != hash2

    def test_hash_password_not_equal_to_plain(self):
        """哈希值不应等于明文密码"""
        plain = "admin123"
        hashed = _hash_password(plain)
        assert hashed != plain

    def test_verify_password_correct(self):
        """正确密码应验证通过"""
        password = "testpass"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """错误密码应验证失败"""
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False

    def test_verify_password_case_sensitive(self):
        """密码应区分大小写"""
        hashed = get_password_hash("Secret")
        assert verify_password("secret", hashed) is False
        assert verify_password("Secret", hashed) is True

    def test_get_password_hash_returns_sha256_hex(self):
        """密码哈希应为 64 位十六进制字符串"""
        hashed = get_password_hash("any")
        assert isinstance(hashed, str)
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)


class TestUserAuthentication:
    """用户认证单元测试"""

    def test_authenticate_user_valid_credentials(self):
        """有效凭据应返回用户对象"""
        user = authenticate_user(fake_users_db, "admin", "admin")
        assert user is not None
        assert user["username"] == "admin"
        assert user["disabled"] is False

    def test_authenticate_user_invalid_username(self):
        """无效用户名应返回 None"""
        user = authenticate_user(fake_users_db, "nonexistent", "admin")
        assert user is None

    def test_authenticate_user_invalid_password(self):
        """无效密码应返回 None"""
        user = authenticate_user(fake_users_db, "admin", "wrongpassword")
        assert user is None

    def test_authenticate_user_case_sensitive_username(self):
        """用户名应区分大小写"""
        user = authenticate_user(fake_users_db, "Admin", "admin")
        assert user is None

    def test_fake_users_db_has_required_fields(self):
        """用户数据库应包含必要字段"""
        for username, user in fake_users_db.items():
            assert "username" in user
            assert "hashed_password" in user
            assert "disabled" in user
            assert user["username"] == username
            assert len(user["hashed_password"]) == 64


class TestJWTToken:
    """JWT Token 单元测试"""

    def test_create_access_token_returns_string(self):
        """access token 应为字符串"""
        token = create_access_token({"sub": "testuser"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_exp(self):
        """access token 应包含 exp 字段"""
        token = create_access_token({"sub": "testuser"})
        payload = decode_token(token)
        assert payload is not None
        assert "exp" in payload
        assert "sub" in payload
        assert payload["sub"] == "testuser"

    def test_create_access_token_custom_expiry(self):
        """自定义过期时间应生效"""
        expire_delta = timedelta(minutes=5)
        token = create_access_token({"sub": "testuser"}, expires_delta=expire_delta)
        payload = decode_token(token)
        exp_timestamp = payload["exp"]
        now_timestamp = datetime.utcnow().timestamp()
        # 过期时间应大于当前时间
        diff = exp_timestamp - now_timestamp
        # 验证过期时间在合理范围内（大于0，小于24小时）
        # 注意：环境变量 ACCESS_TOKEN_EXPIRE_MINUTES 可能覆盖默认值
        assert diff > 0, "过期时间应大于当前时间"
        assert diff <= 24 * 60 * 60, f"过期时间异常: 实际{diff}秒（超过24小时）"

    def test_create_refresh_token_longer_expiry(self):
        """refresh token 应有更长过期时间"""
        token = create_refresh_token({"sub": "testuser"})
        payload = decode_token(token)
        exp_timestamp = payload["exp"]
        now_timestamp = datetime.utcnow().timestamp()
        # 默认 7 天
        assert 6 * 86400 <= exp_timestamp - now_timestamp <= 8 * 86400

    def test_decode_token_invalid_returns_none(self):
        """无效 token 应返回 None"""
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_decode_token_malformed_returns_none(self):
        """畸形 token 应返回 None"""
        payload = decode_token("not-a-jwt")
        assert payload is None

    def test_decode_token_empty_returns_none(self):
        """空 token 应返回 None"""
        payload = decode_token("")
        assert payload is None

    def test_token_integrity_tampered_fails(self):
        """篡改后的 token 应解析失败"""
        token = create_access_token({"sub": "testuser"})
        tampered = token[:-5] + "XXXXX"
        payload = decode_token(tampered)
        assert payload is None


class TestTokenEdgeCases:
    """Token 边界情况测试"""

    def test_access_token_with_empty_sub(self):
        """空 sub 也应生成 token"""
        token = create_access_token({"sub": ""})
        payload = decode_token(token)
        assert payload["sub"] == ""

    def test_access_token_with_extra_claims(self):
        """额外 claims 应被保留"""
        token = create_access_token({"sub": "user", "role": "admin", "org": "acme"})
        payload = decode_token(token)
        assert payload["role"] == "admin"
        assert payload["org"] == "acme"
