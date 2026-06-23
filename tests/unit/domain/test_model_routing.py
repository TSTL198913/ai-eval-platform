"""
模型路由模块专项测试
测试目标：验证 ModelRouter 的路由决策逻辑、熔断器保护、难度估算和监控指标
"""

import json
import os
from unittest.mock import MagicMock, patch

from src.domain.model_routing import ModelRouter, model_router


class TestModelRouterConfiguration:
    """配置加载测试"""

    @patch.dict(os.environ, {"ROUTING_CONFIG": json.dumps({"strategies": {}})})
    def test_config_from_environment_variable(self):
        router = ModelRouter()
        assert "strategies" in router._routing_config

    @patch.dict(os.environ, {"ROUTING_CONFIG_PATH": "/nonexistent/path.json"})
    def test_config_fallback_to_default(self):
        router = ModelRouter()
        assert "security" in router._routing_config.get("strategies", {})

    def test_default_difficulty_rules(self):
        router = ModelRouter()
        rules = router._routing_config.get("difficulty_rules", {})
        assert "complex_keywords" in rules
        assert "simple_keywords" in rules


class TestModelRouterDifficultyEstimation:
    """难度估算测试"""

    def test_high_difficulty_long_input(self):
        router = ModelRouter()
        payload = {"user_input": "x" * 3000, "expected_output": "y" * 500}
        result = router._estimate_difficulty(payload)
        assert result == "high"

    def test_high_difficulty_complex_keywords(self):
        router = ModelRouter()
        payload = {"user_input": "请证明这个数学定理并进行深度分析"}
        result = router._estimate_difficulty(payload)
        assert result == "high"

    def test_low_difficulty_short_input(self):
        router = ModelRouter()
        payload = {"user_input": "你好", "expected_output": "Hi"}
        result = router._estimate_difficulty(payload)
        assert result == "low"

    def test_low_difficulty_simple_keywords(self):
        router = ModelRouter()
        payload = {"user_input": "请翻译这句话"}
        result = router._estimate_difficulty(payload)
        assert result == "low"

    def test_medium_difficulty_default(self):
        router = ModelRouter()
        payload = {
            "user_input": "这是一个长度适中的普通请求，包含足够多的字符以确保不会被判定为短文本",
            "expected_output": "这是一个对应的响应，长度也要足够长以确保不会被判定为短文本",
        }
        result = router._estimate_difficulty(payload)
        assert result == "medium"

    def test_empty_payload_returns_medium(self):
        router = ModelRouter()
        result = router._estimate_difficulty(None)
        assert result == "medium"


class TestModelRouterSemanticComplexity:
    """语义复杂度分析测试"""

    def test_complex_keywords_increase_score(self):
        router = ModelRouter()
        payload = {"user_input": "请证明这个定理并进行优化设计"}
        score = router._analyze_semantic_complexity(payload)
        assert score > 0.5

    def test_simple_keywords_decrease_score(self):
        router = ModelRouter()
        payload = {"user_input": "请总结并提取关键词"}
        score = router._analyze_semantic_complexity(payload)
        assert score < 0.5

    def test_no_keywords_returns_neutral(self):
        router = ModelRouter()
        payload = {"user_input": "普通文本内容"}
        score = router._analyze_semantic_complexity(payload)
        assert score == 0.5


class TestModelRouterRouting:
    """路由决策测试"""

    @patch("src.domain.model_routing.model_performance_analyzer")
    @patch("src.domain.model_routing.load_config")
    def test_routing_with_performance_data(self, mock_load, mock_analyzer):
        mock_analyzer.get_model_recommendations.return_value = [
            {"model_name": "deepseek-chat", "avg_score": 0.9}
        ]
        mock_load.return_value = MagicMock(model_name="deepseek-chat")
        router = ModelRouter()
        decision = router.route("security")
        assert decision["source"] == "performance_based"
        assert decision["confidence"] == 0.9

    @patch("src.domain.model_routing.model_performance_analyzer")
    @patch("src.domain.model_routing.load_config")
    def test_routing_fallback_to_config(self, mock_load, mock_analyzer):
        mock_analyzer.get_model_recommendations.return_value = []
        mock_load.return_value = MagicMock(model_name="deepseek-chat")
        router = ModelRouter()
        decision = router.route("security")
        assert decision["source"] == "config_based"
        assert decision["confidence"] == 0.5

    @patch("src.domain.model_routing.load_config")
    def test_routing_fallback_to_default(self, mock_load):
        mock_load.side_effect = Exception("Config error")
        router = ModelRouter()
        decision = router.route("unknown_type")
        assert decision["source"] == "fallback"
        assert decision["provider"] == "deepseek"

    def test_routing_decision_based_on_difficulty(self):
        router = ModelRouter()

        high_payload = {"user_input": "x" * 3000}
        high_decision = router.get_routing_decision("text", high_payload)
        assert high_decision["strategy"] == "quality"

        low_payload = {"user_input": "hi"}
        low_decision = router.get_routing_decision("text", low_payload)
        assert low_decision["strategy"] == "speed"

        medium_payload = {
            "user_input": "This is a normal request with sufficient length to be classified as medium difficulty",
            "expected_output": "This is a corresponding response",
        }
        medium_decision = router.get_routing_decision("text", medium_payload)
        assert medium_decision["strategy"] == "balanced"


class TestModelRouterCircuitBreaker:
    """熔断器保护测试"""

    def test_circuit_breaker_initial_state(self):
        router = ModelRouter()
        stats = router.get_routing_stats()
        assert stats["circuit_breaker"]["state"] == "closed"

    @patch("src.infra.cache.get_redis_client")
    def test_circuit_breaker_redis_unavailable(self, mock_redis):
        """测试Redis不可用时使用内存熔断器"""
        mock_redis.side_effect = Exception("Redis connection error")

        router = ModelRouter()
        stats = router.get_routing_stats()

        # 应该使用内存熔断器
        assert stats["circuit_breaker"]["state"] == "closed"
        # 验证熔断器正常工作
        assert "failed_calls" in stats["circuit_breaker"]

    def test_circuit_breaker_failure_recording(self):
        router = ModelRouter()

        router._circuit_breaker._record_failure()
        stats = router.get_routing_stats()
        assert stats["circuit_breaker"]["failed_calls"] == 1

    def test_circuit_breaker_success_recording(self):
        router = ModelRouter()
        router._circuit_breaker._record_success()
        stats = router.get_routing_stats()
        assert stats["circuit_breaker"]["successful_calls"] == 1

    def test_stats_reset(self):
        router = ModelRouter()
        router._routing_stats["total_decisions"] = 100
        router._routing_stats["failures"] = 10

        router.reset_routing_stats()
        stats = router.get_routing_stats()
        assert stats["total_decisions"] == 0
        assert stats["failures"] == 0
        assert stats["circuit_breaker"]["state"] == "closed"


class TestModelRouterCreateClient:
    """LLM客户端创建测试"""

    @patch("src.domain.model_routing.create_llm_client")
    @patch("src.domain.model_routing.load_config")
    def test_create_client_success(self, mock_load, mock_create):
        mock_load.return_value = MagicMock(model_name="test-model")
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        router = ModelRouter()
        client, decision = router.create_llm_client("general", {"user_input": "test"})

        assert client == mock_client
        assert decision["source"] != "critical_fallback"

    @patch("src.domain.model_routing.create_llm_client")
    @patch("src.domain.model_routing.load_config")
    def test_create_client_fallback_on_error(self, mock_load, mock_create):
        mock_load.return_value = MagicMock(model_name="test-model")
        mock_create.side_effect = [Exception("API Error"), MagicMock()]

        router = ModelRouter()
        client, decision = router.create_llm_client("general", {"user_input": "test"})

        assert decision["source"] == "fallback_on_error"
        assert router._routing_stats["failures"] == 1


class TestModelRouterMetrics:
    """监控指标测试"""

    @patch("src.domain.model_routing.ROUTING_DECISION_COUNTER")
    @patch("src.domain.model_routing.ROUTING_LATENCY")
    def test_decision_metrics_recorded(self, mock_latency, mock_counter):
        router = ModelRouter()
        router._record_decision("test_source", "test_type", "test_provider", 0.1)

        mock_counter.labels.assert_called_once_with(
            task_type="test_type", provider="test_provider", source="test_source"
        )
        mock_latency.labels.assert_called_once_with(task_type="test_type", source="test_source")

    def test_routing_stats_accumulation(self):
        router = ModelRouter()
        initial_total = router._routing_stats["total_decisions"]

        router._record_decision("performance_based", "security", "openai", 0.1)
        router._record_decision("config_based", "text", "deepseek", 0.05)

        assert router._routing_stats["total_decisions"] == initial_total + 2
        assert router._routing_stats["performance_based"] == 1
        assert router._routing_stats["config_based"] == 1


class TestModelRouterIntegration:
    """集成测试"""

    def test_global_router_instance(self):
        assert model_router is not None
        assert isinstance(model_router, ModelRouter)

    def test_update_config_persists(self):
        router = ModelRouter()
        original_strategies = router._routing_config["strategies"].copy()

        new_strategy = {"test_strategy": {"preference": "quality", "providers": ["openai"]}}
        router.update_routing_config({"strategies": new_strategy})

        assert "test_strategy" in router._routing_config["strategies"]

        router.update_routing_config({"strategies": original_strategies})

    def test_get_available_providers(self):
        router = ModelRouter()
        providers = router.get_available_providers()
        assert "DEEPSEEK" in providers
        assert "OPENAI" in providers
        assert "ANTHROPIC" in providers

    def test_get_routing_config(self):
        """测试获取路由配置"""
        router = ModelRouter()
        config = router.get_routing_config()
        assert "strategies" in config
        assert "difficulty_rules" in config
        assert config == router._routing_config


class TestModelRouterErrorHandling:
    """错误处理测试 - 覆盖异常路径"""

    @patch.dict(os.environ, {"ROUTING_CONFIG": "invalid json {"})
    def test_invalid_json_environment_variable(self):
        """测试无效JSON环境变量"""
        router = ModelRouter()
        # 应该回退到默认配置
        assert "strategies" in router._routing_config
        assert "security" in router._routing_config.get("strategies", {})

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_config_file_load_error(self, mock_open, mock_exists):
        """测试配置文件加载失败"""
        mock_exists.return_value = True
        mock_open.side_effect = Exception("File read error")

        router = ModelRouter()
        # 应该回退到默认配置
        assert "strategies" in router._routing_config

    @patch("src.domain.model_routing.model_performance_analyzer")
    @patch("src.domain.model_routing.load_config")
    def test_performance_analyzer_exception(self, mock_load, mock_analyzer):
        """测试性能分析器抛出异常"""
        mock_analyzer.get_model_recommendations.side_effect = Exception("Analyzer error")
        mock_load.return_value = MagicMock(model_name="deepseek-chat")

        router = ModelRouter()
        decision = router.route("security")

        # 应该回退到配置
        assert decision["source"] in ["config_based", "fallback"]
        assert decision["provider"] in ["deepseek", "openai"]

    @patch("src.domain.model_routing.model_performance_analyzer")
    @patch("src.domain.model_routing.load_config")
    def test_load_config_exception_in_route(self, mock_load, mock_analyzer):
        """测试路由时加载配置抛出异常"""
        mock_analyzer.get_model_recommendations.return_value = [
            {"model_name": "deepseek-chat", "avg_score": 0.9}
        ]
        mock_load.side_effect = Exception("Config error")

        router = ModelRouter()
        decision = router.route("security")

        # 应该继续尝试其他provider或回退
        assert decision["source"] in ["config_based", "fallback"]

    @patch("src.domain.model_routing.ROUTING_DECISION_COUNTER")
    @patch("src.domain.model_routing.ROUTING_LATENCY")
    def test_record_metrics_exception(self, mock_latency, mock_counter):
        """测试记录指标时抛出异常"""
        mock_counter.labels.side_effect = Exception("Metric error")

        router = ModelRouter()
        # 应该静默处理，不抛出异常
        router._record_decision("test_source", "test_type", "test_provider", 0.1)

    @patch("src.domain.model_routing.create_llm_client")
    @patch("src.domain.model_routing.load_config")
    @patch("src.domain.model_routing.model_performance_analyzer")
    def test_create_client_critical_failure(self, mock_analyzer, mock_load, mock_create):
        """测试创建客户端完全失败时的回退"""
        mock_analyzer.get_model_recommendations.side_effect = Exception("Analyzer error")
        mock_load.side_effect = Exception("Config error")
        mock_create.side_effect = [Exception("API Error"), MagicMock()]

        router = ModelRouter()
        client, decision = router.create_llm_client("general", {"user_input": "test"})

        # 应该使用critical_fallback
        assert decision["source"] == "critical_fallback"
        assert decision["provider"] == "deepseek"
        assert router._routing_stats["failures"] >= 1


class TestModelRouterDifficultyEdgeCases:
    """难度估算边界情况测试"""

    def test_semantic_score_exactly_high(self):
        """测试语义分数恰好为0.7"""
        router = ModelRouter()
        # 足够多的复杂关键词使分数达到0.7或以上
        payload = {"user_input": "证明推导分析优化设计"}  # 4个关键词 * 0.15 + 0.5 = 1.1
        result = router._estimate_difficulty(payload)
        assert result == "high"

    def test_semantic_score_exactly_low(self):
        """测试语义分数恰好为0.3"""
        router = ModelRouter()
        # 简单关键词降低分数
        payload = {"user_input": "总结提取翻译分类识别"}  # 5个简单关键词会减到0
        result = router._estimate_difficulty(payload)
        assert result == "low"

    def test_text_field_fallback(self):
        """测试使用text字段而非user_input"""
        router = ModelRouter()
        payload = {"text": "x" * 3000}
        result = router._estimate_difficulty(payload)
        assert result == "high"

    def test_high_output_length_only(self):
        """测试仅输出长度超过阈值"""
        router = ModelRouter()
        payload = {"user_input": "short", "expected_output": "x" * 1500}
        result = router._estimate_difficulty(payload)
        assert result == "high"

    def test_both_fields_empty(self):
        """测试两个字段都为空"""
        router = ModelRouter()
        payload = {"user_input": "", "expected_output": ""}
        result = router._estimate_difficulty(payload)
        # 空字符串长度为0，应该小于low阈值
        assert result == "low"
