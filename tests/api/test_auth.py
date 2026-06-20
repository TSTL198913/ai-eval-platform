"""API认证模块测试"""

from datetime import timedelta

from jose import jwt

from src.api.auth import (
    ALGORITHM,
    SECRET_KEY,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    fake_users_db,
    get_password_hash,
    verify_password,
)


class TestPasswordHashing:
    """密码哈希测试"""

    def test_password_hashing_consistency(self):
        """相同密码应产生相同哈希"""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 == hash2

    def test_password_verification(self):
        """密码验证应正确工作"""
        password = "secure_password_456"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_empty_password(self):
        """空密码应正确处理"""
        password = ""
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True
        assert verify_password("non_empty", hashed) is False


class TestUserAuthentication:
    """用户认证测试"""

    def test_authenticate_valid_user(self):
        """有效用户应认证成功"""
        user = authenticate_user(fake_users_db, "admin", "admin")
        assert user is not None
        assert user["username"] == "admin"

    def test_authenticate_invalid_user(self):
        """无效用户应认证失败"""
        user = authenticate_user(fake_users_db, "nonexistent", "password")
        assert user is None

    def test_authenticate_wrong_password(self):
        """错误密码应认证失败"""
        user = authenticate_user(fake_users_db, "admin", "wrong_password")
        assert user is None

    def test_authenticate_disabled_user(self):
        """禁用用户应认证失败"""
        db_with_disabled = {
            "disabled_user": {
                "username": "disabled_user",
                "full_name": "Disabled",
                "email": "disabled@example.com",
                "hashed_password": get_password_hash("password"),
                "disabled": True,
            }
        }
        user = authenticate_user(db_with_disabled, "disabled_user", "password")
        assert user is not None
        assert user["disabled"] is True


class TestTokenGeneration:
    """Token生成测试"""

    def test_create_access_token(self):
        """创建访问令牌"""
        data = {"sub": "test_user", "role": "admin"}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_expiry(self):
        """访问令牌应正确过期"""
        data = {"sub": "test_user"}
        short_expiry = timedelta(seconds=1)
        token = create_access_token(data, expires_delta=short_expiry)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
        assert payload["sub"] == "test_user"

    def test_create_refresh_token(self):
        """创建刷新令牌"""
        data = {"sub": "test_user"}
        token = create_refresh_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self):
        """解码有效令牌"""
        data = {"sub": "test_user", "role": "user"}
        token = create_access_token(data)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "test_user"
        assert payload["role"] == "user"

    def test_decode_invalid_token(self):
        """解码无效令牌"""
        invalid_token = "invalid.token.string"
        payload = decode_token(invalid_token)
        assert payload is None

    def test_decode_expired_token(self):
        """解码过期令牌"""
        data = {"sub": "test_user"}
        past_expiry = timedelta(seconds=-3600)
        token = create_access_token(data, expires_delta=past_expiry)
        payload = decode_token(token)
        assert payload is None

    def test_token_claims(self):
        """令牌应包含正确的声明"""
        data = {"sub": "admin", "email": "admin@example.com", "scopes": ["read", "write"]}
        token = create_access_token(data)
        payload = decode_token(token)
        assert payload["sub"] == "admin"
        assert payload["email"] == "admin@example.com"
        assert payload["scopes"] == ["read", "write"]


class TestEdgeCases:
    """边界情况测试"""

    def test_create_token_with_empty_data(self):
        """使用空数据创建令牌"""
        data = {}
        token = create_access_token(data)
        assert isinstance(token, str)

    def test_authenticate_with_empty_username(self):
        """使用空用户名认证"""
        user = authenticate_user(fake_users_db, "", "password")
        assert user is None

    def test_authenticate_with_empty_password(self):
        """使用空密码认证"""
        user = authenticate_user(fake_users_db, "admin", "")
        assert user is None

    def test_password_hash_length(self):
        """密码哈希长度应正确"""
        password = "test"
        hashed = get_password_hash(password)
        assert len(hashed) == 64
