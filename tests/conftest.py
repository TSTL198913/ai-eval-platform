"""
Pytest 配置 - 后端测试
提供测试夹具：fakeredis 替代、LLM client mock、共享配置
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

# 确保 src 在路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class FakeRedis:
    """
    最小化的 Redis 假实现，支持本项目使用的核心子集：
    - set(key, value, nx, ex) -> bool
    - get(key) -> bytes | None
    - exists(key) -> int
    - setnx(key, value) -> bool
    - expire(key, seconds) -> bool
    - delete(key) -> int
    - eval(script, num_keys, *args) -> 任意（直接调用传入的 callable）
    - register_script(script) -> ScriptObject
    - hmset/hmget（用于限流器）
    - zadd/zremrangebyscore/zcard（用于滑动窗口）
    """

    def __init__(self):
        self._store: dict[bytes, bytes] = {}
        self._ttls: dict[bytes, float] = {}
        self._zsets: dict[bytes, dict[float, set[bytes]]] = {}
        self._hashes: dict[bytes, dict[bytes, bytes]] = {}
        self._scripts: dict[str, FakeScript] = {}

    def _now(self) -> float:
        import time as _t
        return _t.time()

    def _expired(self, key: bytes) -> bool:
        if key not in self._ttls:
            return False
        if self._now() > self._ttls[key]:
            self._store.pop(key, None)
            self._ttls.pop(key, None)
            return True
        return False

    def set(self, key, value, nx=False, ex=None):
        key = key if isinstance(key, bytes) else key.encode()
        value = value if isinstance(value, bytes) else str(value).encode()
        if nx and key in self._store and not self._expired(key):
            return False
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = self._now() + ex
        return True

    def get(self, key):
        key = key if isinstance(key, bytes) else key.encode()
        if self._expired(key):
            return None
        return self._store.get(key)

    def exists(self, key):
        key = key if isinstance(key, bytes) else key.encode()
        return 1 if (key in self._store and not self._expired(key)) else 0

    def setnx(self, key, value):
        return bool(self.set(key, value, nx=True))

    def expire(self, key, seconds):
        key = key if isinstance(key, bytes) else key.encode()
        if key not in self._store:
            return False
        self._ttls[key] = self._now() + seconds
        return True

    def delete(self, key):
        key = key if isinstance(key, bytes) else key.encode()
        existed = key in self._store
        self._store.pop(key, None)
        self._ttls.pop(key, None)
        return 1 if existed else 0

    def eval(self, script, num_keys, *args):
        # 简化实现：Lua 脚本无法执行，调用方应该 mock 自己的 eval
        # 这里检测两个我们需要的脚本模式
        if "HMSET" in script and "HMGET" in script:
            return self._eval_token_bucket(*args)
        if "ZREMRANGEBYSCORE" in script:
            return self._eval_sliding_window(*args)
        if "expire" in script.lower() and "expire" not in script.split("\n")[0].lower():
            return 1
        # 锁释放/续期脚本：原子地 get 后 del/expire
        if "redis.call" in script and ("del" in script or "expire" in script):
            return self._eval_lock_atomic(num_keys, *args)
        return 1

    def _eval_lock_atomic(self, num_keys, *args):
        # args: KEYS[1..num_keys], ARGV[1..]
        keys = list(args[:num_keys])
        argv = list(args[num_keys:])
        if len(keys) >= 1 and len(argv) >= 1:
            key = keys[0]
            key = key if isinstance(key, bytes) else str(key).encode()
            expected = argv[0]
            expected = expected if isinstance(expected, bytes) else str(expected).encode()
            current = self._store.get(key)
            if current == expected:
                self._store.pop(key, None)
                self._ttls.pop(key, None)
                return 1
        return 0

    def _eval_token_bucket(self, *args):
        # args: capacity, refill_rate, now, requested
        capacity = float(args[0])
        refill_rate = float(args[1])
        now = float(args[2])
        requested = float(args[3])
        # 简单实现：每次都按满桶计算（生产场景应追踪 last_update）
        tokens = capacity
        allowed = 0
        if tokens >= requested:
            tokens -= requested
            allowed = 1
        return [allowed, tokens]

    def _eval_sliding_window(self, *args):
        # args: window_ms, max_calls, now_ms
        max_calls = int(args[1])
        return [1, max_calls - 1]

    def register_script(self, script):
        # 关键：必须按脚本内容匹配，相同字符串共享同一实例
        if script not in self._scripts:
            self._scripts[script] = FakeScript(script)
        return self._scripts[script]

    def hmset(self, key, mapping):
        key = key if isinstance(key, bytes) else key.encode()
        h = self._hashes.setdefault(key, {})
        for k, v in mapping.items():
            k = k if isinstance(k, bytes) else k.encode()
            v = v if isinstance(v, bytes) else str(v).encode()
            h[k] = v

    def hmget(self, key, *fields):
        key = key if isinstance(key, bytes) else key.encode()
        h = self._hashes.get(key, {})
        result = []
        for f in fields:
            f = f if isinstance(f, bytes) else f.encode()
            result.append(h.get(f))
        return result

    def zadd(self, key, score, member):
        key = key if isinstance(key, bytes) else key.encode()
        z = self._zsets.setdefault(key, {})
        score = float(score)
        z.setdefault(score, set()).add(member if isinstance(member, bytes) else str(member).encode())
        return 1

    def zremrangebyscore(self, key, min_score, max_score):
        return 0

    def zcard(self, key):
        key = key if isinstance(key, bytes) else key.encode()
        z = self._zsets.get(key, {})
        return sum(len(v) for v in z.values())


class FakeScript:
    """
    模拟 Redis Lua 脚本对象。
    维护跨调用的状态：token 桶剩余量、滑动窗口计数。
    """
    def __init__(self, script: str):
        self.script = script
        self.sha = hash(script)
        # 持久化状态（key -> 值）
        self._token_state: dict[str, float] = {}
        self._sliding_state: dict[str, int] = {}

    def __call__(self, keys=None, args=None):
        keys = keys or []
        args = args or []
        if "HMSET" in self.script:
            return self._token_bucket(keys, args)
        if "ZREMRANGEBYSCORE" in self.script:
            return self._sliding(keys, args)
        return [1, 99]

    def _token_bucket(self, keys, args):
        key = keys[0] if keys else "default"
        capacity = float(args[0])
        refill_rate = float(args[1])
        now = float(args[2])
        requested = float(args[3])
        # 简化：每次按容量重置（生产环境应按 last_update 补充）
        current = self._token_state.get(key, capacity)
        # 根据时间差补充令牌
        elapsed = 0  # 简化：忽略时间差
        tokens = min(capacity, current)
        allowed = 0
        if tokens >= requested:
            tokens -= requested
            allowed = 1
        self._token_state[key] = tokens
        return [allowed, int(tokens)]

    def _sliding(self, keys, args):
        key = keys[0] if keys else "default"
        max_calls = int(args[1])
        current = self._sliding_state.get(key, 0)
        allowed = 0
        remaining = max_calls - current
        if current < max_calls:
            self._sliding_state[key] = current + 1
            allowed = 1
            remaining = max_calls - current - 1
        return [allowed, remaining]


@pytest.fixture
def fake_redis():
    """提供 FakeRedis 实例。"""
    return FakeRedis()


@pytest.fixture
def mock_llm_client():
    """提供 Mock LLM 客户端。"""
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "gpt-4"
    client.chat = MagicMock(return_value="Mock LLM response")
    return client


@pytest.fixture
def failing_llm_client():
    """提供会失败的 LLM 客户端（用于熔断器测试）。"""
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "failing-model"

    def _fail(*args, **kwargs):
        raise ConnectionError("LLM service unavailable")

    client.chat = MagicMock(side_effect=_fail)
    return client


@pytest.fixture(autouse=True)
def reset_evaluator_registry():
    """
    自动为每个测试重置 EvaluatorFactory 注册表。
    解决测试隔离问题：EvaluatorFactory._registry 是全局单例，
    前一个测试的注册状态会污染后续测试。
    
    使用 force=True 强制重新导入模块，确保每次测试都有干净的注册表。
    """
    from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF

    # 重置注册表和缓存标志
    EF._registry = {}
    from src.domain.evaluators import auto_discover, _EVALUATOR_REGISTRY
    auto_discover._EVALUATOR_REGISTRY = None
    
    # 强制重新发现（清除 sys.modules 缓存后重新导入）
    auto_discover(force=True)
    
    yield EF._registry
