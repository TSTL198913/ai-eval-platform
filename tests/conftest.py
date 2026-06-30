"""
Pytest 配置 - 后端测试
提供测试夹具：fakeredis 替代、LLM client mock、共享配置
"""

import os

# 确保测试环境使用内存数据库
os.environ["TESTING"] = "1"

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
        _ = float(args[1])
        _ = float(args[2])
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
        z.setdefault(score, set()).add(
            member if isinstance(member, bytes) else str(member).encode()
        )
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
        _ = float(args[1])
        _ = float(args[2])
        requested = float(args[3])
        # 简化：每次按容量重置（生产环境应按 last_update 补充）
        current = self._token_state.get(key, capacity)
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


@pytest.fixture(scope="session", autouse=True)
def reset_evaluator_registry_session():
    """
    重置 EvaluatorFactory 注册表并重新发现评估器（session级别）。
    解决测试隔离问题：EvaluatorFactory._registry 是全局单例，
    前一个测试的注册状态会污染后续测试。

    使用 force=True 重新加载评估器模块，使装饰器重新执行。
    embedding_service 已加入 _SKIP_MODULES，不会被重新加载，
    因此 mock_embedding_service 的 patch 不会失效。

    优化：改为 session 级别，只在测试开始时执行一次，
    大幅提升测试性能（从8分钟降至2分钟以内）。
    """
    from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF
    import src.domain.evaluators as eval_module

    EF._registry = {}
    eval_module._EVALUATOR_REGISTRY = None

    eval_module.auto_discover(force=True)


@pytest.fixture(autouse=True)
def mock_redis_cache():
    """
    Mock redis_cache，防止熔断器使用真实 Redis 持久化状态。
    解决测试隔离问题：Redis 持久化导致熔断器状态在测试之间共享。
    """
    from unittest.mock import patch, MagicMock

    mock_redis = MagicMock()
    mock_redis.is_connected = False
    mock_redis.get_circuit_breaker_state.return_value = None
    mock_redis.set_circuit_breaker_state.return_value = None

    with patch("src.distributed.redis_cache.redis_cache", mock_redis):
        yield


@pytest.fixture(autouse=True)
def reset_circuit_breaker_registry():
    """
    重置熔断器注册中心。
    解决测试隔离问题：全局熔断器状态在测试之间共享。

    需要重置两处：
    1. circuit_breaker 模块的 _global_registry
    2. BaseEvaluator 的 _breaker_cache（类级别的缓存）
    """
    import src.distributed.circuit_breaker as cb_module
    from src.domain.evaluators.base import BaseEvaluator

    # 重置全局注册中心
    cb_module._global_registry = None

    # 重置 BaseEvaluator 的类级别熔断器缓存
    BaseEvaluator._breaker_cache = {}


@pytest.fixture(autouse=True)
def mock_embedding_service():
    """
    Mock EmbeddingService，避免测试时下载和加载模型
    支持动态返回相似度值：
    - 相同文本返回 1.0
    - 一个文本包含另一个文本返回 0.9
    - 重叠词比例 > 50% 返回 0.8
    - 重叠词比例 > 25% 返回 0.6
    - 有部分重叠词返回 0.4
    - 无重叠词返回 0.0
    - 空字符串返回 0.5
    支持中英文混合文本，中文使用双字(2-gram)匹配
    """
    from unittest.mock import patch, MagicMock

    def has_chinese(text):
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    def get_ngrams(text, n=2):
        chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
        return set("".join(chars[i : i + n]) for i in range(len(chars) - n + 1))

    def calculate_similarity(text1, text2):
        if text1 == text2:
            return 1.0
        if not text1 or not text2:
            return 0.5

        if has_chinese(text1) or has_chinese(text2):
            ngrams1 = get_ngrams(text1)
            ngrams2 = get_ngrams(text2)
            if not ngrams1 or not ngrams2:
                return 0.5
            common = ngrams1 & ngrams2
            if not common:
                return 0.0
            overlap_ratio = len(common) / min(len(ngrams1), len(ngrams2))
            if overlap_ratio >= 0.5:
                return 0.8
            if overlap_ratio >= 0.25:
                return 0.6
            return 0.4

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.5
        common = words1 & words2
        if not common:
            return 0.0
        overlap_ratio = len(common) / min(len(words1), len(words2))
        if overlap_ratio >= 0.5:
            return 0.8
        if overlap_ratio >= 0.25:
            return 0.6
        return 0.4

    with patch("src.domain.evaluators.embedding_service.EmbeddingService") as MockEmbeddingService:
        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.calculate_similarity.side_effect = calculate_similarity
        mock_instance.calculate_similarity_async.side_effect = calculate_similarity
        MockEmbeddingService.get_instance.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_sentence_transformer():
    """
    Mock SentenceTransformer，防止模型加载
    """
    from unittest.mock import patch, MagicMock

    with patch("sentence_transformers.SentenceTransformer") as MockST:
        mock_model = MagicMock()
        MockST.return_value = mock_model
        yield mock_model


# ========================================
# 真实Redis测试支持
# ========================================


@pytest.fixture(scope="session")
def real_redis():
    """
    提供真实Redis连接（session级别）。

    使用条件：
    - 设置环境变量 REDIS_HOST=localhost
    - 或运行 pytest --redis-host=localhost

    如果Redis不可用，将跳过相关测试。
    """
    import os

    redis_host = os.environ.get("REDIS_HOST", None)
    redis_port = int(os.environ.get("REDIS_PORT", 6379))

    if redis_host is None:
        pytest.skip("REDIS_HOST not set, skipping real Redis tests")
        return None

    try:
        import redis

        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        client.ping()
        yield client
        # 清理
        client.flushall()
        client.close()
    except ImportError:
        pytest.skip("redis-py not installed")
    except Exception as e:
        pytest.skip(f"Redis connection failed: {e}")


@pytest.fixture
def clean_redis(real_redis):
    """
    每个测试前清理Redis数据。
    用于需要干净Redis状态的测试。
    """
    if real_redis:
        real_redis.flushall()
    yield real_redis
    if real_redis:
        real_redis.flushall()


# ========================================
# 超时和异常LLM客户端
# ========================================


@pytest.fixture
def timeout_llm_client():
    """
    提供超时的LLM客户端。
    用于测试LLM调用超时后的降级行为。
    """
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "timeout-model"

    def _timeout(*args, **kwargs):
        raise TimeoutError("LLM request timeout after 30 seconds")

    client.chat = MagicMock(side_effect=_timeout)
    return client


@pytest.fixture
def rate_limited_llm_client():
    """
    提供被限流的LLM客户端。
    用于测试API限流处理。
    """
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "rate-limited-model"

    def _rate_limit(*args, **kwargs):
        raise Exception("Rate limit exceeded. Please retry after 60 seconds.")

    client.chat = MagicMock(side_effect=_rate_limit)
    return client


@pytest.fixture
def slow_llm_client():
    """
    提供慢速LLM客户端（延迟响应）。
    用于测试长时间等待的处理。
    """
    import time

    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "slow-model"

    def _slow_response(*args, **kwargs):
        time.sleep(5)  # 模拟5秒延迟
        return "Delayed response"

    client.chat = MagicMock(side_effect=_slow_response)
    return client


@pytest.fixture
def empty_response_llm_client():
    """
    提供返回空响应的LLM客户端。
    用于测试空响应处理。
    """
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "empty-model"

    client.chat = MagicMock(return_value="")
    return client


@pytest.fixture
def malformed_json_llm_client():
    """
    提供返回格式错误JSON的LLM客户端。
    用于测试JSON解析降级。
    """
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "malformed-model"

    client.chat = MagicMock(return_value="{invalid json response")
    return client


# ========================================
# 测试标记注册
# ========================================


def pytest_configure(config):
    """注册自定义测试标记"""
    config.addinivalue_line("markers", "redis: 需要真实Redis环境的测试")
    config.addinivalue_line("markers", "slow: 慢速测试，可能需要较长时间")
    config.addinivalue_line("markers", "stress: 压力测试，高并发或大数据量")
    config.addinivalue_line("markers", "blackbox: 黑盒测试，仅通过公共API验证")
    config.addinivalue_line("markers", "contract: 契约测试，验证接口契约")
