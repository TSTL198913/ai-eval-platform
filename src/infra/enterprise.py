"""
企业版 v1.0

包含：
1. 多租户管理
2. SLA 保障
3. 资源隔离
4. 企业级功能
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TenantTier(Enum):
    """租户等级"""

    FREE = "free"  # 免费版
    PROFESSIONAL = "professional"  # 专业版
    ENTERPRISE = "enterprise"  # 企业版
    PREMIUM = "premium"  # 高级企业版


class SLAType(Enum):
    """SLA 类型"""

    BASIC = "basic"  # 99.5% 可用性
    STANDARD = "standard"  # 99.9% 可用性
    PREMIUM = "premium"  # 99.99% 可用性
    ULTRA = "ultra"  # 99.999% 可用性


@dataclass
class SLAConfig:
    """SLA 配置"""

    sla_type: SLAType
    availability_target: float  # 可用性目标
    response_time_p99_ms: float  # P99 响应时间目标
    support_response_hours: int  # 支持响应时间（小时）
    monthly_price: float  # 月费
    features: list[str] = field(default_factory=list)


# SLA 配置映射
SLA_CONFIGS: dict[SLAType, SLAConfig] = {
    SLAType.BASIC: SLAConfig(
        sla_type=SLAType.BASIC,
        availability_target=99.5,
        response_time_p99_ms=500,
        support_response_hours=48,
        monthly_price=999,
        features=["basic_api", "email_support"],
    ),
    SLAType.STANDARD: SLAConfig(
        sla_type=SLAType.STANDARD,
        availability_target=99.9,
        response_time_p99_ms=200,
        support_response_hours=24,
        monthly_price=9999,
        features=["full_api", "priority_support", "custom_datasets"],
    ),
    SLAType.PREMIUM: SLAConfig(
        sla_type=SLAType.PREMIUM,
        availability_target=99.99,
        response_time_p99_ms=100,
        support_response_hours=4,
        monthly_price=99999,
        features=[
            "full_api",
            "24x7_support",
            "custom_models",
            "dedicated_resources",
        ],
    ),
    SLAType.ULTRA: SLAConfig(
        sla_type=SLAType.ULTRA,
        availability_target=99.999,
        response_time_p99_ms=50,
        support_response_hours=1,
        monthly_price=999999,
        features=[
            "full_api",
            "instant_support",
            "custom_all",
            "dedicated_cluster",
            "on_site_support",
        ],
    ),
}


@dataclass
class Tenant:
    """租户"""

    tenant_id: str
    name: str
    tier: TenantTier
    sla_type: SLAType
    created_at: float = field(default_factory=time.time)
    is_active: bool = True
    resource_quota: dict[str, int] = field(default_factory=dict)
    usage_stats: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_sla_config(self) -> SLAConfig:
        """获取 SLA 配置"""
        return SLA_CONFIGS.get(self.sla_type, SLA_CONFIGS[SLAType.BASIC])

    def check_quota(self, resource: str, amount: int) -> bool:
        """检查资源配额"""
        quota = self.resource_quota.get(resource, 0)
        used = self.usage_stats.get(resource, 0)
        return used + amount <= quota

    def record_usage(self, resource: str, amount: float):
        """记录使用量"""
        current = self.usage_stats.get(resource, 0)
        self.usage_stats[resource] = current + amount


@dataclass
class TenantResource:
    """租户资源"""

    tenant_id: str
    resource_type: str  # cpu, memory, storage, api_calls
    allocated: int
    used: int = 0
    reserved: int = 0

    def get_available(self) -> int:
        """获取可用资源"""
        return self.allocated - self.used - self.reserved

    def get_usage_ratio(self) -> float:
        """获取使用比例"""
        return self.used / self.allocated if self.allocated > 0 else 0


class TenantManager:
    """
    租户管理器

    管理多租户的创建、配置、资源分配等。
    """

    def __init__(self):
        self._tenants: dict[str, Tenant] = {}
        self._resources: dict[str, dict[str, TenantResource]] = {}
        self._isolated_pools: dict[str, Any] = {}

    def create_tenant(
        self,
        name: str,
        tier: TenantTier,
        sla_type: SLAType,
        resource_quota: dict[str, int] | None = None,
    ) -> Tenant:
        """创建租户"""
        import uuid

        tenant_id = str(uuid.uuid4())

        # 设置默认配额
        default_quotas = {
            TenantTier.FREE: {"api_calls": 100, "storage": 100},
            TenantTier.PROFESSIONAL: {"api_calls": 10000, "storage": 10000},
            TenantTier.ENTERPRISE: {"api_calls": 100000, "storage": 100000},
            TenantTier.PREMIUM: {"api_calls": -1, "storage": -1},  # 无限
        }

        quota = resource_quota or default_quotas.get(tier, {})

        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            tier=tier,
            sla_type=sla_type,
            resource_quota=quota,
        )

        self._tenants[tenant_id] = tenant
        self._resources[tenant_id] = {}

        # 初始化资源
        for resource_type, amount in quota.items():
            self._resources[tenant_id][resource_type] = TenantResource(
                tenant_id=tenant_id,
                resource_type=resource_type,
                allocated=amount if amount > 0 else 1000000,  # 无限设为大值
            )

        logger.info(f"Created tenant {tenant_id}: {name} ({tier.value})")
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """获取租户"""
        return self._tenants.get(tenant_id)

    def get_tenant_resources(self, tenant_id: str) -> dict[str, TenantResource]:
        """获取租户资源"""
        return self._resources.get(tenant_id, {})

    def allocate_resource(self, tenant_id: str, resource_type: str, amount: int) -> bool:
        """分配资源"""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return False

        resources = self._resources.get(tenant_id, {})
        resource = resources.get(resource_type)

        if not resource:
            return False

        if resource.get_available() < amount:
            logger.warning(f"Tenant {tenant_id} resource {resource_type} exhausted")
            return False

        resource.used += amount
        tenant.record_usage(resource_type, amount)

        return True

    def release_resource(self, tenant_id: str, resource_type: str, amount: int) -> bool:
        """释放资源"""
        resources = self._resources.get(tenant_id, {})
        resource = resources.get(resource_type)

        if resource:
            resource.used = max(0, resource.used - amount)
            return True

        return False

    def get_tenant_usage_report(self, tenant_id: str) -> dict:
        """获取租户使用报告"""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return {}

        resources = self._resources.get(tenant_id, {})

        return {
            "tenant_id": tenant_id,
            "name": tenant.name,
            "tier": tenant.tier.value,
            "sla": tenant.get_sla_config().sla_type.value,
            "usage": tenant.usage_stats,
            "resources": {
                r_type: {
                    "allocated": r.allocated,
                    "used": r.used,
                    "available": r.get_available(),
                    "usage_ratio": r.get_usage_ratio(),
                }
                for r_type, r in resources.items()
            },
        }

    def list_tenants(self) -> list[Tenant]:
        """列出所有租户"""
        return list(self._tenants.values())


class SLAMonitor:
    """
    SLA 监控器

    监控 SLA 达成情况。
    """

    def __init__(self):
        self._metrics: dict[str, dict[str, list[float]]] = {}
        self._incidents: dict[str, list[dict]] = {}

    def record_metric(self, tenant_id: str, metric_type: str, value: float):
        """记录指标"""
        if tenant_id not in self._metrics:
            self._metrics[tenant_id] = {}

        if metric_type not in self._metrics[tenant_id]:
            self._metrics[tenant_id][metric_type] = []

        self._metrics[tenant_id][metric_type].append(value)

        # 只保留最近 1000 条
        if len(self._metrics[tenant_id][metric_type]) > 1000:
            self._metrics[tenant_id][metric_type].pop(0)

    def calculate_availability(self, tenant_id: str) -> float:
        """计算可用性"""
        metrics = self._metrics.get(tenant_id, {})
        success_metrics = metrics.get("success", [])
        total_metrics = metrics.get("total", [])

        if not total_metrics:
            return 100.0

        total_requests = sum(total_metrics)
        successful_requests = sum(success_metrics)

        return (successful_requests / total_requests * 100) if total_requests > 0 else 100.0

    def calculate_p99_latency(self, tenant_id: str) -> float:
        """计算 P99 延迟"""
        metrics = self._metrics.get(tenant_id, {})
        latencies = metrics.get("latency", [])

        if not latencies:
            return 0.0

        sorted_latencies = sorted(latencies)
        return sorted_latencies[int(len(sorted_latencies) * 0.99)]

    def check_sla_compliance(self, tenant: Tenant) -> dict:
        """检查 SLA 合规性"""
        sla_config = tenant.get_sla_config()

        availability = self.calculate_availability(tenant.tenant_id)
        p99_latency = self.calculate_p99_latency(tenant.tenant_id)

        return {
            "tenant_id": tenant.tenant_id,
            "sla_type": sla_config.sla_type.value,
            "availability": {
                "target": sla_config.availability_target,
                "actual": availability,
                "compliant": availability >= sla_config.availability_target,
            },
            "response_time": {
                "target_p99": sla_config.response_time_p99_ms,
                "actual_p99": p99_latency,
                "compliant": p99_latency <= sla_config.response_time_p99_ms,
            },
            "overall_compliant": (
                availability >= sla_config.availability_target
                and p99_latency <= sla_config.response_time_p99_ms
            ),
        }

    def record_incident(self, tenant_id: str, incident_type: str, details: dict):
        """记录 SLA 事故"""
        if tenant_id not in self._incidents:
            self._incidents[tenant_id] = []

        incident = {
            "incident_id": f"inc-{int(time.time())}",
            "tenant_id": tenant_id,
            "type": incident_type,
            "timestamp": time.time(),
            "details": details,
        }

        self._incidents[tenant_id].append(incident)
        logger.warning(f"SLA incident recorded: {incident_type} for tenant {tenant_id}")

    def get_incidents(self, tenant_id: str) -> list[dict]:
        """获取事故列表"""
        return self._incidents.get(tenant_id, [])


class EnterpriseFeatures:
    """
    企业级功能

    提供企业版专属功能。
    """

    def __init__(self):
        self._custom_models: dict[str, dict] = {}
        self._custom_datasets: dict[str, dict] = {}
        self._audit_logs: dict[str, list] = {}

    def register_custom_model(self, tenant_id: str, model_name: str, model_config: dict):
        """注册自定义模型"""
        key = f"{tenant_id}:{model_name}"
        self._custom_models[key] = {
            "tenant_id": tenant_id,
            "model_name": model_name,
            "config": model_config,
            "created_at": time.time(),
        }
        logger.info(f"Custom model registered: {model_name} for tenant {tenant_id}")

    def get_custom_models(self, tenant_id: str) -> list[dict]:
        """获取租户的自定义模型"""
        return [m for key, m in self._custom_models.items() if m["tenant_id"] == tenant_id]

    def register_custom_dataset(self, tenant_id: str, dataset_name: str, dataset_data: dict):
        """注册自定义数据集"""
        key = f"{tenant_id}:{dataset_name}"
        self._custom_datasets[key] = {
            "tenant_id": tenant_id,
            "dataset_name": dataset_name,
            "data": dataset_data,
            "created_at": time.time(),
        }
        logger.info(f"Custom dataset registered: {dataset_name} for tenant {tenant_id}")

    def get_custom_datasets(self, tenant_id: str) -> list[dict]:
        """获取租户的自定义数据集"""
        return [d for key, d in self._custom_datasets.items() if d["tenant_id"] == tenant_id]

    def log_audit(self, tenant_id: str, action: str, details: dict):
        """记录审计日志"""
        if tenant_id not in self._audit_logs:
            self._audit_logs[tenant_id] = []

        log_entry = {
            "timestamp": time.time(),
            "action": action,
            "details": details,
        }

        self._audit_logs[tenant_id].append(log_entry)

        # 只保留最近 1000 条
        if len(self._audit_logs[tenant_id]) > 1000:
            self._audit_logs[tenant_id].pop(0)

    def get_audit_logs(self, tenant_id: str, limit: int = 100) -> list[dict]:
        """获取审计日志"""
        logs = self._audit_logs.get(tenant_id, [])
        return logs[-limit:]


class EnterpriseManager:
    """
    企业版管理器

    综合管理多租户、SLA、企业功能。
    """

    def __init__(self):
        self._tenant_manager = TenantManager()
        self._sla_monitor = SLAMonitor()
        self._enterprise_features = EnterpriseFeatures()

    def create_enterprise_tenant(self, name: str, sla_type: SLAType = SLAType.STANDARD) -> Tenant:
        """创建企业租户"""
        return self._tenant_manager.create_tenant(
            name=name,
            tier=TenantTier.ENTERPRISE,
            sla_type=sla_type,
        )

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """获取租户"""
        return self._tenant_manager.get_tenant(tenant_id)

    def check_sla(self, tenant_id: str) -> dict:
        """检查 SLA"""
        tenant = self._tenant_manager.get_tenant(tenant_id)
        if tenant:
            return self._sla_monitor.check_sla_compliance(tenant)
        return {}

    def get_enterprise_report(self, tenant_id: str) -> dict:
        """获取企业报告"""
        tenant = self._tenant_manager.get_tenant(tenant_id)
        if not tenant:
            return {}

        return {
            "tenant": self._tenant_manager.get_tenant_usage_report(tenant_id),
            "sla": self.check_sla(tenant_id),
            "custom_models": self._enterprise_features.get_custom_models(tenant_id),
            "custom_datasets": self._enterprise_features.get_custom_datasets(tenant_id),
            "audit_logs": self._enterprise_features.get_audit_logs(tenant_id, 50),
        }


# 全局企业版管理器
_global_enterprise: EnterpriseManager | None = None


def get_enterprise_manager() -> EnterpriseManager:
    """获取全局企业版管理器"""
    global _global_enterprise
    if _global_enterprise is None:
        _global_enterprise = EnterpriseManager()
    return _global_enterprise
