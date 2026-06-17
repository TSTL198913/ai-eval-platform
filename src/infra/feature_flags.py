from typing import Any, Dict, Optional
from enum import Enum


class FeatureFlag(Enum):
    PRIORITY_BUFFER = "priority_buffer"
    ADAPTIVE_BATCH_SIZE = "adaptive_batch_size"
    ASYNC_EVALUATION = "async_evaluation"
    COST_GOVERNANCE = "cost_governance"
    IDENTITY_CHECK = "identity_check"
    CIRCUIT_BREAKER = "circuit_breaker"
    RATE_LIMITER = "rate_limiter"
    CACHE_ENABLED = "cache_enabled"
    METRICS_ENABLED = "metrics_enabled"
    TRACING_ENABLED = "tracing_enabled"


class FeatureManager:
    _instance: Optional["FeatureManager"] = None
    _features: Dict[str, bool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._features = {
                FeatureFlag.PRIORITY_BUFFER.value: False,
                FeatureFlag.ADAPTIVE_BATCH_SIZE.value: True,
                FeatureFlag.ASYNC_EVALUATION.value: True,
                FeatureFlag.COST_GOVERNANCE.value: True,
                FeatureFlag.IDENTITY_CHECK.value: True,
                FeatureFlag.CIRCUIT_BREAKER.value: True,
                FeatureFlag.RATE_LIMITER.value: True,
                FeatureFlag.CACHE_ENABLED.value: True,
                FeatureFlag.METRICS_ENABLED.value: True,
                FeatureFlag.TRACING_ENABLED.value: True,
            }
        return cls._instance

    def is_enabled(self, feature: FeatureFlag) -> bool:
        return self._features.get(feature.value, False)

    def enable(self, feature: FeatureFlag) -> None:
        self._features[feature.value] = True

    def disable(self, feature: FeatureFlag) -> None:
        self._features[feature.value] = False

    def toggle(self, feature: FeatureFlag) -> bool:
        current = self.is_enabled(feature)
        self._features[feature.value] = not current
        return not current

    def set(self, feature: FeatureFlag, value: bool) -> None:
        self._features[feature.value] = value

    def get_all_features(self) -> Dict[str, bool]:
        return dict(self._features)

    def load_from_config(self, config: Dict[str, Any]) -> None:
        for key, value in config.items():
            if key in self._features:
                self._features[key] = bool(value)


feature_manager = FeatureManager()