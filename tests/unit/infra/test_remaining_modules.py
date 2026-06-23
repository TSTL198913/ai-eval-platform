"""
剩余Infra模块专项测试
测试目标：验证security、structured_logging等模块
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.infra.security import (
    decrypt_api_key,
    decrypt_value,
    encrypt_api_key,
    encrypt_value,
    generate_key,
    load_key,
    mask_api_key,
    mask_sensitive_value,
    mask_url,
    safe_getenv,
    save_key,
)
from src.infra.structured_logging import (
    get_span_id,
    get_trace_id,
    request_id_var,
    set_request_context,
    set_trace_context,
    set_user_context,
    span_id_var,
    trace_id_var,
    user_id_var,
)


class TestSecurity:
    """Security安全模块测试"""

    def test_generate_key(self):
        """生成加密密钥"""
        key = generate_key("test-password")
        assert len(key) > 0

    def test_encrypt_decrypt_value(self):
        """加密和解密值"""
        key = generate_key("test-password")
        original = "test-value"

        encrypted = encrypt_value(original, key)
        decrypted = decrypt_value(encrypted, key)

        assert encrypted != original
        assert decrypted == original

    def test_encrypt_decrypt_api_key(self):
        """加密和解密API密钥"""
        key = generate_key("test-password")
        original = "sk-1234567890abcdef"

        encrypted = encrypt_api_key(original, key)
        decrypted = decrypt_api_key(encrypted, key)

        assert encrypted != original
        assert decrypted == original

    def test_mask_api_key(self):
        """脱敏API密钥"""
        result = mask_api_key("sk-1234567890abcdef")
        assert result.startswith("sk-")
        assert result.endswith("****")

    def test_mask_sensitive_value(self):
        """脱敏敏感值"""
        result = mask_sensitive_value("secret-password")
        assert "****" in result

    def test_mask_url(self):
        """脱敏URL"""
        result = mask_url("https://user:password@example.com")
        assert result is not None

    def test_safe_getenv(self):
        """安全获取环境变量"""
        os.environ["TEST_VAR"] = "test-value"
        result = safe_getenv("TEST_VAR")
        assert result == "test-value"

        result = safe_getenv("NON_EXISTENT_VAR", "default")
        assert result == "default"

    def test_load_save_key(self):
        """加载和保存密钥"""
        key = generate_key("test-password")

        with patch("src.infra.security.encrypted_config.open", MagicMock()):
            save_key(key, "test.key")
            loaded = load_key("test.key")

            assert loaded == key


class TestStructuredLogging:
    """StructuredLogging结构化日志测试"""

    def test_trace_id_var_default(self):
        """trace_id_var默认值"""
        assert trace_id_var.get() == ""

    def test_span_id_var_default(self):
        """span_id_var默认值"""
        assert span_id_var.get() == ""

    def test_user_id_var_default(self):
        """user_id_var默认值"""
        assert user_id_var.get() == ""

    def test_request_id_var_default(self):
        """request_id_var默认值"""
        assert request_id_var.get() == ""

    def test_set_and_get_trace_context(self):
        """设置和获取追踪上下文"""
        set_trace_context("test-trace-id", "test-span-id")

        assert get_trace_id() == "test-trace-id"
        assert get_span_id() == "test-span-id"

        trace_id_var.set("")
        span_id_var.set("")

    def test_set_trace_context_without_span(self):
        """设置追踪上下文不含span_id"""
        set_trace_context("test-trace-id")

        assert get_trace_id() == "test-trace-id"

        trace_id_var.set("")

    def test_set_user_context(self):
        """设置用户上下文"""
        set_user_context("user-123")

        assert user_id_var.get() == "user-123"

        user_id_var.set("")

    def test_set_request_context(self):
        """设置请求上下文"""
        set_request_context("req-123")

        assert request_id_var.get() == "req-123"

        request_id_var.set("")
