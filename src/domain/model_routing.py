import json
import logging
import os
import time
from typing import Any

from src.distributed.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from src.domain.model_performance import model_performance_analyzer
from src.domain.models.llm_factory import ModelProvider, create_llm_client, load_config
from src.infra.monitoring.metrics import ROUTING_DECISION_COUNTER, ROUTING_LATENCY

logger = logging.getLogger(__name__)


class ModelRoutingStrategy:
    BALANCED = "balanced"
    QUALITY = "quality"
    SPEED = "speed"
    COST = "cost"


class ModelRouter:
    def __init__(self):
        self._routing_config = self._load_routing_config()
        self._default_provider = ModelProvider.DEEPSEEK
        self._circuit_breaker = self._init_circuit_breaker()
        self._routing_stats = {
            "total_decisions": 0,
            "performance_based": 0,
            "config_based": 0,
            "fallback": 0,
            "failures": 0,
            "last_reset": time.time(),
        }

    def _init_circuit_breaker(self) -> CircuitBreaker:
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=15.0,
            half_open_max_calls=2,
        )
        try:
            from src.infra.cache import get_redis_client

            redis_client = get_redis_client()
            return CircuitBreaker("model_routing", config=config, redis_client=redis_client)
        except Exception:
            logger.warning("Redis not available, using in-memory circuit breaker")
            return CircuitBreaker("model_routing", config=config)

    def _load_routing_config(self) -> dict[str, Any]:
        config = self._get_default_config()

        env_config = os.getenv("ROUTING_CONFIG")
        if env_config:
            try:
                env_data = json.loads(env_config)
                config.update(env_data)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in ROUTING_CONFIG environment variable")

        config_path = os.getenv("ROUTING_CONFIG_PATH", "config/routing_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, encoding="utf-8") as f:
                    file_data = json.load(f)
                    config.update(file_data)
            except Exception as e:
                logger.warning(f"Failed to load routing config from {config_path}: {e}")

        return config

    def _get_default_config(self) -> dict[str, Any]:
        return {
            "strategies": {
                "security": {"preference": "quality", "providers": ["openai", "anthropic"]},
                "code": {"preference": "quality", "providers": ["deepseek", "openai"]},
                "finance": {"preference": "quality", "providers": ["openai", "qwen"]},
                "text": {"preference": "balanced", "providers": ["deepseek", "qwen"]},
                "general": {"preference": "balanced", "providers": ["deepseek", "qwen", "ollama"]},
                "sentiment": {"preference": "speed", "providers": ["qwen", "ollama"]},
                "classification": {"preference": "speed", "providers": ["ollama", "qwen"]},
                "translation": {"preference": "balanced", "providers": ["deepseek", "qwen"]},
                "llm_as_judge": {"preference": "quality", "providers": ["openai", "anthropic"]},
            },
            "fallback_provider": "deepseek",
            "confidence_threshold": 0.7,
            "difficulty_rules": {
                "high_input_length": 2000,
                "high_output_length": 1000,
                "low_input_length": 20,
                "low_output_length": 20,
                "complex_keywords": ["证明", "推导", "分析", "优化", "设计"],
                "simple_keywords": ["总结", "提取", "翻译", "分类", "识别"],
            },
        }

    def _analyze_semantic_complexity(self, payload: dict[str, Any]) -> float:
        user_input = payload.get("user_input", "") or payload.get("text", "")
        expected_output = payload.get("expected_output", "")

        complexity_score = 0.5
        config = self._routing_config.get("difficulty_rules", {})

        complex_keywords = config.get("complex_keywords", [])
        simple_keywords = config.get("simple_keywords", [])

        for keyword in complex_keywords:
            if keyword in user_input or keyword in expected_output:
                complexity_score += 0.15

        for keyword in simple_keywords:
            if keyword in user_input or keyword in expected_output:
                complexity_score -= 0.1

        return max(0.0, min(1.0, complexity_score))

    def _estimate_difficulty(self, payload: dict[str, Any] = None) -> str:
        if not payload:
            return "medium"

        semantic_score = self._analyze_semantic_complexity(payload)

        if semantic_score >= 0.7:
            return "high"

        if semantic_score <= 0.3:
            return "low"

        config = self._routing_config.get("difficulty_rules", {})
        user_input = payload.get("user_input", "") or payload.get("text", "")
        expected_output = payload.get("expected_output", "")

        input_length = len(user_input)
        output_length = len(expected_output)

        high_input = config.get("high_input_length", 2000)
        high_output = config.get("high_output_length", 1000)
        low_input = config.get("low_input_length", 20)
        low_output = config.get("low_output_length", 20)

        if input_length > high_input or output_length > high_output:
            return "high"
        elif input_length < low_input and output_length < low_output:
            return "low"
        else:
            return "medium"

    def route(
        self, task_type: str, strategy: str = ModelRoutingStrategy.BALANCED
    ) -> dict[str, Any]:
        start_time = time.time()
        strategy_config = self._routing_config.get("strategies", {}).get(task_type)
        if strategy_config:
            preference = strategy
            providers = strategy_config.get("providers", [])
        else:
            preference = strategy
            providers = [self._default_provider]

        try:
            recommendations = model_performance_analyzer.get_model_recommendations(
                task_type, preference=preference
            )
        except Exception as e:
            logger.error(f"Failed to get model recommendations: {e}")
            recommendations = []

        if recommendations:
            best_model = recommendations[0]
            for provider in providers:
                try:
                    config = load_config(provider)
                    if config.model_name == best_model.get("model_name"):
                        latency = time.time() - start_time
                        self._record_decision("performance_based", task_type, provider, latency)
                        return {
                            "provider": provider,
                            "model_name": config.model_name,
                            "strategy": preference,
                            "confidence": best_model.get("avg_score", 0),
                            "source": "performance_based",
                            "latency_ms": latency * 1000,
                        }
                except Exception as e:
                    logger.warning(f"Failed to load config for {provider}: {e}")
                    continue

        if providers:
            provider = providers[0]
            try:
                config = load_config(provider)
                latency = time.time() - start_time
                self._record_decision("config_based", task_type, provider, latency)
                return {
                    "provider": provider,
                    "model_name": config.model_name,
                    "strategy": preference,
                    "confidence": 0.5,
                    "source": "config_based",
                    "latency_ms": latency * 1000,
                }
            except Exception as e:
                logger.warning(f"Failed to load config for {provider}: {e}")
                pass

        latency = time.time() - start_time
        self._record_decision("fallback", task_type, self._default_provider, latency)
        return {
            "provider": self._default_provider,
            "model_name": "deepseek-chat",
            "strategy": preference,
            "confidence": 0.3,
            "source": "fallback",
            "latency_ms": latency * 1000,
        }

    def _record_decision(self, source: str, task_type: str, provider: str, latency: float):
        self._routing_stats["total_decisions"] += 1
        self._routing_stats[source] = self._routing_stats.get(source, 0) + 1

        try:
            ROUTING_DECISION_COUNTER.labels(
                task_type=task_type,
                provider=provider,
                source=source,
            ).inc()
            ROUTING_LATENCY.labels(
                task_type=task_type,
                source=source,
            ).observe(latency)
        except Exception as e:
            logger.warning(f"Failed to record routing metrics: {e}")

    def get_routing_decision(
        self, task_type: str, payload: dict[str, Any] = None
    ) -> dict[str, Any]:
        difficulty = self._estimate_difficulty(payload)
        logger.debug(f"Task {task_type} difficulty estimated as: {difficulty}")

        if difficulty == "high":
            return self.route(task_type, ModelRoutingStrategy.QUALITY)
        elif difficulty == "low":
            return self.route(task_type, ModelRoutingStrategy.SPEED)
        else:
            return self.route(task_type, ModelRoutingStrategy.BALANCED)

    def create_llm_client(self, task_type: str, payload: dict[str, Any] = None) -> Any:
        start_time = time.time()
        try:
            decision = self.get_routing_decision(task_type, payload)

            try:
                llm_client = create_llm_client(
                    provider=decision["provider"],
                    config=load_config(decision["provider"]),
                )
                latency = time.time() - start_time
                logger.info(
                    f"Model routing success: task_type={task_type}, "
                    f"provider={decision['provider']}, "
                    f"model={decision['model_name']}, "
                    f"source={decision['source']}, "
                    f"latency={latency:.3f}s"
                )
                return llm_client, decision
            except Exception as e:
                latency = time.time() - start_time
                logger.error(
                    f"Failed to create LLM client for {decision['provider']}: {e}, "
                    f"latency={latency:.3f}s"
                )
                self._routing_stats["failures"] += 1
                self._circuit_breaker._record_failure()
                fallback_client = create_llm_client(provider=self._default_provider)
                decision["source"] = "fallback_on_error"
                decision["latency_ms"] = latency * 1000
                return fallback_client, decision

        except Exception as e:
            latency = time.time() - start_time
            logger.error(
                f"Model routing failed completely: {e}, "
                f"task_type={task_type}, "
                f"latency={latency:.3f}s"
            )
            self._routing_stats["failures"] += 1
            self._circuit_breaker._record_failure()
            fallback_client = create_llm_client(provider=self._default_provider)
            return fallback_client, {
                "provider": self._default_provider,
                "model_name": "deepseek-chat",
                "strategy": "balanced",
                "confidence": 0.1,
                "source": "critical_fallback",
                "latency_ms": latency * 1000,
            }

    def update_routing_config(self, new_config: dict[str, Any]):
        self._routing_config.update(new_config)
        config_path = os.getenv("ROUTING_CONFIG_PATH", "config/routing_config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self._routing_config, f, ensure_ascii=False, indent=2)
        logger.info("Routing config updated")

    def get_routing_config(self) -> dict[str, Any]:
        return self._routing_config

    def get_available_providers(self) -> list[str]:
        return [attr for attr in dir(ModelProvider) if not attr.startswith("_")]

    def get_routing_stats(self) -> dict[str, Any]:
        stats = dict(self._routing_stats)
        stats["circuit_breaker"] = self._circuit_breaker.get_stats()
        return stats

    def reset_routing_stats(self):
        self._routing_stats = {
            "total_decisions": 0,
            "performance_based": 0,
            "config_based": 0,
            "fallback": 0,
            "failures": 0,
            "last_reset": time.time(),
        }
        self._circuit_breaker.reset()
        logger.info("Routing stats and circuit breaker reset")


model_router = ModelRouter()
