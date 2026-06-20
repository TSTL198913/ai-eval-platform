import json
import os
from typing import Any

from src.domain.model_performance import model_performance_analyzer
from src.domain.models.llm_factory import ModelProvider, create_llm_client, load_config


class ModelRoutingStrategy:
    BALANCED = 'balanced'
    QUALITY = 'quality'
    SPEED = 'speed'
    COST = 'cost'


class ModelRouter:
    def __init__(self):
        self._routing_config = self._load_routing_config()
        self._default_provider = ModelProvider.DEEPSEEK

    def _load_routing_config(self) -> dict[str, Any]:
        config_path = 'config/routing_config.json'
        if os.path.exists(config_path):
            try:
                with open(config_path, encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return self._get_default_config()

    def _get_default_config(self) -> dict[str, Any]:
        return {
            'strategies': {
                'security': {'preference': 'quality', 'providers': ['openai', 'anthropic']},
                'code': {'preference': 'quality', 'providers': ['deepseek', 'openai']},
                'finance': {'preference': 'quality', 'providers': ['openai', 'qwen']},
                'text': {'preference': 'balanced', 'providers': ['deepseek', 'qwen']},
                'general': {'preference': 'balanced', 'providers': ['deepseek', 'qwen', 'ollama']},
                'sentiment': {'preference': 'speed', 'providers': ['qwen', 'ollama']},
                'classification': {'preference': 'speed', 'providers': ['ollama', 'qwen']},
                'translation': {'preference': 'balanced', 'providers': ['deepseek', 'qwen']},
                'llm_as_judge': {'preference': 'quality', 'providers': ['openai', 'anthropic']},
            },
            'fallback_provider': 'deepseek',
            'confidence_threshold': 0.7,
        }

    def route(self, task_type: str, strategy: str = ModelRoutingStrategy.BALANCED) -> dict[str, Any]:
        strategy_config = self._routing_config.get('strategies', {}).get(task_type)
        if strategy_config:
            preference = strategy_config.get('preference', strategy)
            providers = strategy_config.get('providers', [])
        else:
            preference = strategy
            providers = [self._default_provider]

        recommendations = model_performance_analyzer.get_model_recommendations(
            task_type, preference=preference
        )

        if recommendations:
            best_model = recommendations[0]
            for provider in providers:
                try:
                    config = load_config(provider)
                    if config.model_name == best_model.get('model_name'):
                        return {
                            'provider': provider,
                            'model_name': config.model_name,
                            'strategy': preference,
                            'confidence': best_model.get('avg_score', 0),
                            'source': 'performance_based',
                        }
                except Exception:
                    continue

        if providers:
            provider = providers[0]
            try:
                config = load_config(provider)
                return {
                    'provider': provider,
                    'model_name': config.model_name,
                    'strategy': preference,
                    'confidence': 0.5,
                    'source': 'config_based',
                }
            except Exception:
                pass

        return {
            'provider': self._default_provider,
            'model_name': 'deepseek-chat',
            'strategy': preference,
            'confidence': 0.3,
            'source': 'fallback',
        }

    def get_routing_decision(self, task_type: str, payload: dict[str, Any] = None) -> dict[str, Any]:
        difficulty = self._estimate_difficulty(payload)
        if difficulty == 'high':
            return self.route(task_type, ModelRoutingStrategy.QUALITY)
        elif difficulty == 'low':
            return self.route(task_type, ModelRoutingStrategy.SPEED)
        else:
            return self.route(task_type, ModelRoutingStrategy.BALANCED)

    def _estimate_difficulty(self, payload: dict[str, Any] = None) -> str:
        if not payload:
            return 'medium'

        user_input = payload.get('user_input', '') or payload.get('text', '')
        expected_output = payload.get('expected_output', '')

        input_length = len(user_input)
        output_length = len(expected_output)

        if input_length > 2000 or output_length > 1000:
            return 'high'
        elif input_length < 50 and output_length < 50:
            return 'low'
        else:
            return 'medium'

    def create_llm_client(self, task_type: str, payload: dict[str, Any] = None) -> Any:
        decision = self.get_routing_decision(task_type, payload)
        try:
            return create_llm_client(
                provider=decision['provider'],
                config=load_config(decision['provider']),
            ), decision
        except Exception:
            return create_llm_client(provider=self._default_provider), decision

    def update_routing_config(self, new_config: dict[str, Any]):
        self._routing_config.update(new_config)
        config_path = 'config/routing_config.json'
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self._routing_config, f, ensure_ascii=False, indent=2)

    def get_routing_config(self) -> dict[str, Any]:
        return self._routing_config

    def get_available_providers(self) -> list[str]:
        return list(ModelProvider.__members__.keys())


model_router = ModelRouter()
