"""
安全模块

包含：
1. RBAC 权限控制（角色、权限、API密钥管理）
2. 敏感信息加密、脱敏、环境变量安全加载
"""

from src.infra.security.encrypted_config import (
    EncryptedConfig,
    SecureLogger,
    decrypt_api_key,
    decrypt_value,
    encrypt_api_key,
    encrypt_value,
    generate_key,
    load_env_with_override,
    load_key,
    mask_api_key,
    mask_sensitive_value,
    mask_url,
    safe_getenv,
    save_key,
)
from src.infra.security.rbac import (
    ROLE_PERMISSIONS,
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

__all__ = [
    # RBAC
    "Permission",
    "Role",
    "ROLE_PERMISSIONS",
    "APIKey",
    "AuditLog",
    "APIKeyManager",
    "PermissionChecker",
    "AuditLogger",
    "RequestSigner",
    "SecurityManager",
    "get_security",
    # Encryption
    "encrypt_api_key",
    "decrypt_api_key",
    "encrypt_value",
    "decrypt_value",
    "mask_api_key",
    "mask_sensitive_value",
    "mask_url",
    "load_key",
    "save_key",
    "generate_key",
    "EncryptedConfig",
    "SecureLogger",
    "safe_getenv",
    "load_env_with_override",
]
