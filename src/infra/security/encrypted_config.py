"""
敏感信息加密模块

功能：
1. 环境变量加密/解密（使用Fernet对称加密）
2. API Key安全存储
3. 敏感信息脱敏

依赖：
    pip install cryptography

使用方式：
    # 加密API Key
    from src.infra.security.encrypted_config import encrypt_api_key
    encrypted = encrypt_api_key("sk-xxx")
    print(f"加密后的值: {encrypted}")

    # 解密API Key（需要密钥文件）
    from src.infra.security.encrypted_config import decrypt_api_key, load_key
    key = load_key("data/.key")
    decrypted = decrypt_api_key(encrypted, key)
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography库未安装，敏感信息加密功能不可用")


# =====================================================================
# 密钥管理
# =====================================================================


def generate_key(password: str, salt: bytes | None = None) -> bytes:
    """生成加密密钥

    Args:
        password: 密钥密码
        salt: 盐值（如果不提供则随机生成）

    Returns:
        加密密钥（Base64编码）
    """
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography库未安装")

    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def load_key(key_path: str) -> bytes:
    """从文件加载密钥"""
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography库未安装")

    key_file = Path(key_path)
    if not key_file.exists():
        raise FileNotFoundError(f"密钥文件不存在: {key_path}")

    return key_file.read_bytes()


def save_key(key: bytes, key_path: str):
    """保存密钥到文件"""
    key_file = Path(key_path)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_bytes(key)
    # 设置文件权限（仅所有者可读写）
    os.chmod(key_path, 0o600)
    logger.info(f"密钥已保存到: {key_path}")


# =====================================================================
# 加密/解密
# =====================================================================


def encrypt_value(value: str, key: bytes) -> str:
    """加密字符串值"""
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography库未安装")

    fernet = Fernet(key)
    encrypted = fernet.encrypt(value.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_value(encrypted: str, key: bytes) -> str:
    """解密字符串值"""
    if not HAS_CRYPTO:
        raise RuntimeError("cryptography库未安装")

    fernet = Fernet(key)
    encrypted_bytes = base64.urlsafe_b64decode(encrypted.encode())
    return fernet.decrypt(encrypted_bytes).decode()


def encrypt_api_key(api_key: str, key: bytes | None = None) -> str:
    """加密API Key"""
    if key is None:
        # 使用默认密钥（生产环境应从安全存储加载）
        key = os.getenv("ENCRYPTION_KEY", "").encode()
        if not key:
            logger.warning("未设置ENCRYPTION_KEY，使用临时密钥")
            key = generate_key("temp-key-change-in-production")

    return encrypt_value(api_key, key)


def decrypt_api_key(encrypted_key: str, key: bytes | None = None) -> str:
    """解密API Key"""
    if key is None:
        key = os.getenv("ENCRYPTION_KEY", "").encode()
        if not key:
            raise ValueError("必须设置ENCRYPTION_KEY环境变量")

    return decrypt_value(encrypted_key, key)


# =====================================================================
# 敏感信息脱敏
# =====================================================================


def mask_sensitive_value(value: str, visible_chars: int = 4) -> str:
    """脱敏敏感值，只显示前N个字符

    Examples:
        mask_sensitive_value("sk-1234567890", 4) -> "sk-12...****"
        mask_sensitive_value("password123", 3) -> "pas...****"
    """
    if len(value) <= visible_chars:
        return "*" * len(value)

    return value[:visible_chars] + "..." + "*" * 4


def mask_api_key(api_key: str) -> str:
    """脱敏API Key"""
    if not api_key:
        return ""

    # 常见API Key格式
    if api_key.startswith("sk-"):
        # OpenAI格式
        return mask_sensitive_value(api_key, 5)
    elif api_key.startswith("sk-") and len(api_key) > 20:
        # DeepSeek格式
        return mask_sensitive_value(api_key, 8)
    elif api_key.startswith("AIza"):
        # Google API格式
        return mask_sensitive_value(api_key, 5)
    elif api_key.startswith("amzn."):
        # AWS格式
        return mask_sensitive_value(api_key, 6)

    # 默认脱敏
    return mask_sensitive_value(api_key, 4)


def mask_url(url: str) -> str:
    """脱敏URL中的敏感信息"""
    if not url:
        return ""

    import re

    # 脱敏API Key参数
    url = re.sub(r"([?&]api[_-]?key=)([^&]+)", r"\1***", url, flags=re.IGNORECASE)

    # 脱敏token参数
    url = re.sub(r"([?&]token=)([^&]+)", r"\1***", url, flags=re.IGNORECASE)

    # 脱敏password参数
    url = re.sub(r"([?&]password=)([^&]+)", r"\1***", url, flags=re.IGNORECASE)

    return url


# =====================================================================
# 配置加密存储
# =====================================================================


class EncryptedConfig:
    """加密配置管理器"""

    def __init__(self, config_file: str, key: bytes | None = None):
        self.config_file = Path(config_file)
        self.key = key or os.getenv("ENCRYPTION_KEY", "").encode()
        if not self.key:
            raise ValueError("必须设置ENCRYPTION_KEY环境变量")
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self):
        """加载配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    encrypted_data = f.read()
                    if encrypted_data.strip():
                        decrypted = decrypt_value(encrypted_data, self.key)
                        self._config = json.loads(decrypted)
            except Exception as e:
                logger.error(f"配置加载失败: {e}")

    def _save(self):
        """保存配置"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            encrypted = encrypt_value(json.dumps(self._config), self.key)
            f.write(encrypted)
        os.chmod(str(self.config_file), 0o600)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """设置配置值"""
        self._config[key] = value
        self._save()

    def get_api_key(self, name: str) -> str | None:
        """获取加密的API Key"""
        encrypted = self._config.get(f"api_key_{name}")
        if encrypted:
            return decrypt_api_key(encrypted, self.key)
        return None

    def set_api_key(self, name: str, api_key: str):
        """存储加密的API Key"""
        self._config[f"api_key_{name}"] = encrypt_api_key(api_key, self.key)
        self._save()


# =====================================================================
# 安全日志记录
# =====================================================================


class SecureLogger:
    """安全日志处理器，自动脱敏敏感信息"""

    SENSITIVE_PATTERNS = [
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?([\w-]+)', r"api_key=***"),
        (r'token["\']?\s*[:=]\s*["\']?([\w.-]+)', r"token=***"),
        (r'password["\']?\s*[:=]\s*["\']?([^\s"\']+)', r"password=***"),
        (r'Authorization["\']?\s*[:=]\s*["\']?Bearer\s+([\w.-]+)', r"Authorization=Bearer ***"),
    ]

    @classmethod
    def sanitize(cls, message: str) -> str:
        """脱敏日志消息"""
        import re

        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
        return message


# =====================================================================
# 环境变量安全加载
# =====================================================================


def safe_getenv(key: str, default: str | None = None, required: bool = False) -> str | None:
    """安全获取环境变量

    Args:
        key: 环境变量名
        default: 默认值
        required: 是否必须存在

    Returns:
        环境变量值
    """
    value = os.getenv(key, default)

    if required and value is None:
        raise ValueError(f"必须设置环境变量: {key}")

    return value


def load_env_with_override(env_file: str = ".env.encrypted") -> dict[str, str]:
    """加载加密的环境变量文件

    文件格式（JSON加密后）：
    {
        "DEEPSEEK_API_KEY": "gAAAAAB...",
        "OPENAI_API_KEY": "gAAAAAB..."
    }
    """
    env_path = Path(env_file)

    if not env_path.exists():
        logger.warning(f"加密环境变量文件不存在: {env_file}")
        return {}

    try:
        key = os.getenv("ENCRYPTION_KEY", "").encode()
        if not key:
            logger.error("未设置ENCRYPTION_KEY，无法解密环境变量")
            return {}

        with open(env_path) as f:
            encrypted = f.read()

        decrypted = decrypt_value(encrypted, key)
        config = json.loads(decrypted)

        # 设置到环境变量
        for k, v in config.items():
            os.environ[k] = v

        logger.info(f"已加载加密环境变量: {env_file}")
        return config

    except Exception as e:
        logger.error(f"环境变量加载失败: {e}")
        return {}
