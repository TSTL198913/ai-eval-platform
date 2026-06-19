import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.infra.db.repository import EvaluationRepository
from src.infra.cost_governance import cost_governance


class ModelPerformanceAnalyzer:
    def __init__(self):
        self._repository = EvaluationRepository()
        self._performance_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_updated_at: float = 0

    def analyze_model_performance(self, model_name: str, evaluator_type: str = None, days: int = 7) -> Dict[str, Any]:
        records = self._repository.search(
            evaluator=evaluator_type,
            limit=1000,
        )

        model_records = [r for r in records if r.get('model_name') == model_name]

        if not model_records:
            return {
                'model_name': model_name,
                'total_evaluations': 0,
                'avg_score': 0.0,
                'pass_rate': 0.0,
                'avg_latency_ms': 0.0,
                'evaluator_type': evaluator_type or 'all',
            }

        scores = []
        passed = 0
        latencies = []

        for record in model_records:
            response_data = record.get('response_data', {})
            score = response_data.get('score')
            if score is not None:
                scores.append(score)
            if record.get('status') == 'passed':
                passed += 1
            latencies.append(record.get('latency_ms', 0))

        return {
            'model_name': model_name,
            'total_evaluations': len(model_records),
            'avg_score': sum(scores) / len(scores) if scores else 0.0,
            'pass_rate': passed / len(model_records) if model_records else 0.0,
            'avg_latency_ms': sum(latencies) / len(latencies) if latencies else 0.0,
            'evaluator_type': evaluator_type or 'all',
            'analysis_time': datetime.utcnow().isoformat(),
        }

    def compare_models(self, model_names: List[str], evaluator_type: str = None) -> List[Dict[str, Any]]:
        results = []
        for model_name in model_names:
            perf = self.analyze_model_performance(model_name, evaluator_type)
            cost_info = self._get_model_cost(model_name)
            perf.update(cost_info)
            results.append(perf)
        return sorted(results, key=lambda x: x.get('avg_score', 0), reverse=True)

    def _get_model_cost(self, model_name: str) -> Dict[str, float]:
        top_models = cost_governance.get_top_models_by_cost(limit=10)
        for model in top_models:
            if model['model_name'] == model_name:
                return {'total_cost_usd': model['total_cost']}
        return {'total_cost_usd': 0.0}

    def get_pareto_frontier(self, evaluator_type: str = None) -> List[Dict[str, Any]]:
        all_records = self._repository.search(evaluator=evaluator_type, limit=2000)
        model_groups: Dict[str, Dict[str, List[float]]] = {}

        for record in all_records:
            model_name = record.get('model_name', 'unknown')
            if model_name not in model_groups:
                model_groups[model_name] = {'scores': [], 'latencies': [], 'count': 0}
            response_data = record.get('response_data', {})
            score = response_data.get('score')
            if score is not None:
                model_groups[model_name]['scores'].append(score)
            model_groups[model_name]['latencies'].append(record.get('latency_ms', 0))
            model_groups[model_name]['count'] += 1

        model_stats = []
        for model_name, data in model_groups.items():
            if data['scores']:
                avg_score = sum(data['scores']) / len(data['scores'])
                avg_latency = sum(data['latencies']) / len(data['latencies'])
                model_stats.append({
                    'model_name': model_name,
                    'avg_score': avg_score,
                    'avg_latency_ms': avg_latency,
                    'total_evaluations': data['count'],
                })

        if not model_stats:
            return []

        sorted_stats = sorted(model_stats, key=lambda x: (x['avg_score'], -x['avg_latency_ms']), reverse=True)

        frontier = []
        best_latency = float('inf')
        for stat in sorted_stats:
            if stat['avg_latency_ms'] < best_latency:
                frontier.append(stat)
                best_latency = stat['avg_latency_ms']

        return frontier

    def get_model_recommendations(self, task_type: str, preference: str = 'balanced') -> List[Dict[str, Any]]:
        frontier = self.get_pareto_frontier(task_type)
        if not frontier:
            return []

        if preference == 'quality':
            return [frontier[0]]
        elif preference == 'speed':
            return [frontier[-1]]
        else:
            mid = len(frontier) // 2
            return frontier[max(0, mid-1):min(len(frontier), mid+2)]

    def update_performance_cache(self):
        self._performance_cache.clear()
        all_records = self._repository.search(limit=1000)
        for record in all_records:
            model_name = record.get('model_name', 'unknown')
            if model_name not in self._performance_cache:
                self._performance_cache[model_name] = {'scores': [], 'latencies': []}
            response_data = record.get('response_data', {})
            score = response_data.get('score')
            if score is not None:
                self._performance_cache[model_name]['scores'].append(score)
            self._performance_cache[model_name]['latencies'].append(record.get('latency_ms', 0))
        self._cache_updated_at = datetime.utcnow().timestamp()

    def get_cached_performance(self, model_name: str) -> Optional[Dict[str, Any]]:
        if (datetime.utcnow().timestamp() - self._cache_updated_at) > 3600:
            self.update_performance_cache()

        data = self._performance_cache.get(model_name)
        if not data or not data['scores']:
            return None

        return {
            'model_name': model_name,
            'avg_score': sum(data['scores']) / len(data['scores']),
            'avg_latency_ms': sum(data['latencies']) / len(data['latencies']),
            'sample_count': len(data['scores']),
        }

    def analyze_all_models(self, evaluator_type: str = None) -> List[Dict[str, Any]]:
        all_records = self._repository.search(evaluator=evaluator_type, limit=2000)
        model_names = set(record.get('model_name', 'unknown') for record in all_records)
        results = []
        for model_name in model_names:
            perf = self.analyze_model_performance(model_name, evaluator_type)
            if perf['total_evaluations'] > 0:
                results.append(perf)
        return sorted(results, key=lambda x: x.get('avg_score', 0), reverse=True)


model_performance_analyzer = ModelPerformanceAnalyzer()
