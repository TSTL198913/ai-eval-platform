"""
成本治理模块 - 分布式版本

监控和控制 LLM API 调用的成本和延迟，支持：
1. 本地模式：进程内存存储（单实例）
2. Redis 模式：分布式存储（多 Worker 共享）

使用 Redis Stream + 原子计数器实现分布式环境下的数据一致性。
"""

import logging
import threading
import time
from enum import Enum

from pydantic import BaseModel, Field

from src.config import settings

logger = logging.getLogger(__name__)


class StorageMode(Enum):
    """存储模式"""

    LOCAL = "local"  # 本地内存模式
    REDIS = "redis"  # Redis 分布式模式


class TokenUsage(BaseModel):
    prompt_tokens: int = Field(0, description="提示词Token数")
    completion_tokens: int = Field(0, description="回答Token数")
    total_tokens: int = Field(0, description="总Token数")


class CostRecord(BaseModel):
    record_id: str = Field(..., description="记录ID")
    model_name: str = Field(..., description="模型名称")
    usage: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = Field(0.0, description="成本(美元)")
    latency_ms: float = Field(0.0, description="延迟(毫秒)")
    request_type: str = Field("evaluation", description="请求类型")
    timestamp: float = Field(default_factory=time.time, description="时间戳")


class CostMetrics(BaseModel):
    daily_cost_usd: float = Field(0.0, description="日成本")
    weekly_cost_usd: float = Field(0.0, description="周成本")
    monthly_cost_usd: float = Field(0.0, description="月成本")
    avg_latency_ms: float = Field(0.0, description="平均延迟")
    p50_latency_ms: float = Field(0.0, description="P50延迟")
    p95_latency_ms: float = Field(0.0, description="P95延迟")
    p99_latency_ms: float = Field(0.0, description="P99延迟")
    total_requests: int = Field(0, description="总请求数")
    avg_tokens_per_request: float = Field(0.0, description="平均Token数")


class CostGovernance:
    """成本治理模块

    支持两种存储模式：
    - LOCAL: 本地内存存储，适合单实例部署
    - REDIS: Redis 分布式存储，适合多 Worker 部署
    """

    MODEL_COSTS = {
        "gpt-4": {"prompt": 0.00003, "completion": 0.00006},
        "gpt-3.5-turbo": {"prompt": 0.0000015, "completion": 0.000002},
        "claude-3": {"prompt": 0.000008, "completion": 0.000024},
        "gemini-pro": {"prompt": 0.000001, "completion": 0.0000015},
        "default": {"prompt": 0.000002, "completion": 0.000002},
    }

    def __init__(
        self,
        daily_cost_limit: float | None = None,
        weekly_cost_limit: float | None = None,
        monthly_cost_limit: float | None = None,
        storage_mode: StorageMode = StorageMode.LOCAL,
        redis_url: str | None = None,
    ):
        """
        初始化成本治理模块

        Args:
            daily_cost_limit: 日预算限制
            weekly_cost_limit: 周预算限制
            monthly_cost_limit: 月预算限制
            storage_mode: 存储模式 (LOCAL/REDIS)
            redis_url: Redis 连接 URL (Redis 模式必填)
        """
        # 本地存储
        self.records: list[CostRecord] = []
        self._records_lock = threading.Lock()

        # 预算限制
        self.daily_cost_limit = (
            daily_cost_limit
            if daily_cost_limit is not None
            else settings.__dict__.get("daily_cost_limit", 100.0)
        )
        self.weekly_cost_limit = (
            weekly_cost_limit
            if weekly_cost_limit is not None
            else settings.__dict__.get("weekly_cost_limit", 500.0)
        )
        self.monthly_cost_limit = (
            monthly_cost_limit
            if monthly_cost_limit is not None
            else settings.__dict__.get("monthly_cost_limit", 2000.0)
        )
        self.hourly_request_limit = settings.__dict__.get("hourly_request_limit", 10000)

        # Redis 配置
        self.storage_mode = storage_mode
        self._redis_client = None
        if storage_mode == StorageMode.REDIS:
            self._init_redis_client(redis_url)

    def _init_redis_client(self, redis_url: str | None = None):
        """初始化 Redis 客户端"""
        try:
            from src.infra.redis_stream_client import RedisStreamClient

            url = redis_url or settings.redis_url
            self._redis_client = RedisStreamClient(url)
            if not self._redis_client.health_check():
                logger.warning("Redis 健康检查失败，切换到本地模式")
                self.storage_mode = StorageMode.LOCAL
                self._redis_client = None
            else:
                logger.info("Redis 连接成功，使用分布式成本治理")
        except Exception as e:
            logger.warning(f"Redis 初始化失败: {e}，切换到本地模式")
            self.storage_mode = StorageMode.LOCAL
            self._redis_client = None

    @property
    def is_distributed(self) -> bool:
        """是否使用分布式模式"""
        return self.storage_mode == StorageMode.REDIS and self._redis_client is not None

    def calculate_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        """计算成本"""
        costs = self.MODEL_COSTS.get(model_name.lower(), self.MODEL_COSTS["default"])
        return (prompt_tokens * costs["prompt"]) + (completion_tokens * costs["completion"])

    def record_usage(
        self,
        record_id: str,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0,
        request_type: str = "evaluation",
    ) -> CostRecord:
        """
        记录使用量

        根据存储模式选择本地存储或 Redis 分布式存储
        """
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = self.calculate_cost(model_name, prompt_tokens, completion_tokens)

        record = CostRecord(
            record_id=record_id,
            model_name=model_name,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            request_type=request_type,
        )

        if self.is_distributed:
            # Redis 分布式模式：原子写入
            return self._record_usage_redis(record)
        else:
            # 本地模式：线程安全写入
            return self._record_usage_local(record)

    def _record_usage_local(self, record: CostRecord) -> CostRecord:
        """本地模式记录"""
        with self._records_lock:
            self.records.append(record)
        return record

    def _record_usage_redis(self, record: CostRecord) -> CostRecord:
        """Redis 模式记录"""
        record_data = record.model_dump(mode="json")

        try:
            new_total, redis_record_id = self._redis_client.atomic_record_and_accumulate(
                record_data=record_data,
                cost_increment=record.cost_usd,
            )
            logger.debug(f"Redis 原子写入成功: {redis_record_id}, total={new_total}")
        except Exception as e:
            logger.error(f"Redis 写入失败，回退到本地模式: {e}")
            # Redis 失败时回退到本地模式
            return self._record_usage_local(record)

        return record

    def get_metrics(self, hours: int | None = None) -> CostMetrics:
        """
        获取指标

        Redis 模式下从 Redis 聚合获取指标
        """
        if self.is_distributed:
            return self._get_metrics_redis()
        else:
            return self._get_metrics_local(hours)

    def _get_metrics_local(self, hours: int | None = None) -> CostMetrics:
        """本地模式获取指标"""
        with self._records_lock:
            if hours is not None:
                if hours <= 0:
                    return CostMetrics()
                cutoff_time = time.time() - (hours * 3600)
                filtered_records = [r for r in self.records if r.timestamp > cutoff_time]
            else:
                filtered_records = list(self.records)

        return self._calculate_metrics(filtered_records)

    def _get_metrics_redis(self) -> CostMetrics:
        """Redis 模式获取指标"""
        try:
            daily_cost = self._redis_client.get_daily_cost()
            records_count = self._redis_client.get_records_count()

            # 从 Redis Stream 读取记录用于计算延迟统计
            records_data = self._redis_client.read_records(count=1000)

            # 重建 CostRecord 对象用于指标计算
            records = []
            for _, data in records_data:
                records.append(CostRecord(**data))

            metrics = self._calculate_metrics(records)
            metrics.daily_cost_usd = daily_cost
            metrics.total_requests = records_count

            return metrics

        except Exception as e:
            logger.error(f"Redis 读取失败: {e}")
            return CostMetrics()

    def _calculate_metrics(self, records: list[CostRecord]) -> CostMetrics:
        """计算指标"""
        if not records:
            return CostMetrics()

        now = time.time()
        day_cutoff = now - 86400
        week_cutoff = now - 604800
        month_cutoff = now - 2592000

        daily_cost = sum(r.cost_usd for r in records if r.timestamp > day_cutoff)
        weekly_cost = sum(r.cost_usd for r in records if r.timestamp > week_cutoff)
        monthly_cost = sum(r.cost_usd for r in records if r.timestamp > month_cutoff)

        latencies = [r.latency_ms for r in records]
        latencies.sort()

        total_tokens = sum(r.usage.total_tokens for r in records)

        return CostMetrics(
            daily_cost_usd=daily_cost,
            weekly_cost_usd=weekly_cost,
            monthly_cost_usd=monthly_cost,
            avg_latency_ms=sum(latencies) / len(latencies),
            p50_latency_ms=latencies[len(latencies) // 2] if latencies else 0,
            p95_latency_ms=latencies[int(len(latencies) * 0.95)] if latencies else 0,
            p99_latency_ms=latencies[int(len(latencies) * 0.99)] if latencies else 0,
            total_requests=len(records),
            avg_tokens_per_request=total_tokens / len(records) if records else 0,
        )

    def check_budget(self) -> dict[str, bool | float]:
        """检查预算"""
        metrics = self.get_metrics()
        if self.daily_cost_limit <= 0:
            return {
                "daily_budget_ok": False,
                "daily_usage_percent": 100.0 if metrics.daily_cost_usd > 0 else 0.0,
            }
        return {
            "daily_budget_ok": metrics.daily_cost_usd < self.daily_cost_limit,
            "daily_usage_percent": (metrics.daily_cost_usd / self.daily_cost_limit * 100),
        }

    def record_request(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        model_name: str = "default",
        latency_ms: float = 0,
    ) -> CostRecord:
        """简化版记录请求（兼容测试接口）"""
        with self._records_lock:
            record_id = f"req_{len(self.records)}"
            record = CostRecord(
                record_id=record_id,
                model_name=model_name,
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
                cost_usd=cost_usd,
                latency_ms=latency_ms,
            )
            self.records.append(record)
            return record

    def get_top_models_by_cost(self, limit: int = 5) -> list[dict[str, float]]:
        """获取成本最高的模型"""
        if self.is_distributed:
            # Redis 模式下从 Redis Stream 读取
            try:
                records_data = self._redis_client.read_records(count=10000)
                records = [CostRecord(**data) for _, data in records_data]
            except Exception as e:
                logger.error(f"从 Redis 读取失败: {e}")
                records = []
        else:
            with self._records_lock:
                records = list(self.records)

        model_costs: dict[str, float] = {}
        for record in records:
            model_costs[record.model_name] = model_costs.get(record.model_name, 0) + record.cost_usd

        return sorted(
            [{"model_name": k, "total_cost": v} for k, v in model_costs.items()],
            key=lambda x: x["total_cost"],
            reverse=True,
        )[:limit]

    def get_top_requests_by_latency(self, limit: int = 10) -> list[CostRecord]:
        """获取延迟最高的请求"""
        with self._records_lock:
            records = list(self.records)
        return sorted(records, key=lambda r: r.latency_ms, reverse=True)[:limit]

    def clear_local_cache(self):
        """清除本地缓存（Redis 模式下使用）"""
        with self._records_lock:
            self.records.clear()

    def sync_from_redis(self):
        """从 Redis 同步数据到本地（Redis 模式下使用）"""
        if not self.is_distributed:
            return

        try:
            records_data = self._redis_client.read_records(count=10000)
            with self._records_lock:
                self.records = [CostRecord(**data) for _, data in records_data]
            logger.info(f"从 Redis 同步 {len(self.records)} 条记录到本地")
        except Exception as e:
            logger.error(f"从 Redis 同步失败: {e}")


# 全局实例 - 默认本地模式
cost_governance = CostGovernance()


def create_distributed_cost_governance(
    redis_url: str | None = None,
) -> CostGovernance:
    """创建分布式成本治理实例"""
    return CostGovernance(
        storage_mode=StorageMode.REDIS,
        redis_url=redis_url,
    )
