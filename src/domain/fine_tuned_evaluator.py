"""
轻量化 Fine-tuned 评估器
使用本地部署的小模型进行快速评估，支持回退到 LLM Client
"""

import json
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class ModelStatus(Enum):
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"
    OFFLINE = "offline"


@dataclass
class ModelInfo:
    name: str
    path: str
    size_mb: float
    status: ModelStatus = ModelStatus.OFFLINE
    avg_latency_ms: float = 0.0
    total_requests: int = 0


class FineTunedEvaluator(BaseEvaluator):
    """轻量化 Fine-tuned 评估器

    支持：
    - 本地部署的小模型（Qwen/Phi/DeepSeek）
    - 自动回退到 LLM Client
    - 性能监控和缓存
    """

    def __init__(
        self,
        model_path: str = None,
        model_name: str = "fine_tuned_judge",
        fallback_to_llm: bool = True,
        max_retries: int = 1
    ):
        super().__init__()
        self._model_path = model_path
        self._model_name = model_name
        self._fallback_to_llm = fallback_to_llm
        self._max_retries = max_retries
        self._model = None
        self._tokenizer = None
        self._status = ModelStatus.OFFLINE
        self._load_model()

    def _load_model(self):
        """加载本地模型"""
        if not self._model_path or not os.path.exists(self._model_path):
            self._status = ModelStatus.OFFLINE
            return

        try:
            self._status = ModelStatus.LOADING
            # 延迟导入，避免不必要的依赖
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_path,
                trust_remote_code=True
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_path,
                device_map="auto",
                trust_remote_code=True
            )
            self._status = ModelStatus.READY
        except ImportError:
            self._status = ModelStatus.FAILED
            print("Warning: transformers not installed, using LLM fallback")
        except Exception as e:
            self._status = ModelStatus.FAILED
            print(f"Warning: Failed to load model: {e}")

    @property
    def model_info(self) -> ModelInfo:
        size_mb = 0.0
        if self._model_path and os.path.exists(self._model_path):
            size_mb = sum(
                os.path.getsize(os.path.join(self._model_path, f))
                for f in os.listdir(self._model_path)
                if os.path.isfile(os.path.join(self._model_path, f))
            ) / (1024 * 1024)

        return ModelInfo(
            name=self._model_name,
            path=self._model_path or "not_loaded",
            size_mb=round(size_mb, 2),
            status=self._status
        )

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """执行评估"""
        user_input = self.get_input_text(request)
        actual_output = self.get_payload_data(request, "actual_output")
        dimensions = self.get_payload_data(request, "dimensions", ["correctness"])

        if not user_input or not actual_output:
            return DomainResponse(is_valid=False, error="user_input/text 和 actual_output 不能为空")

        # 如果本地模型可用，使用本地模型
        if self._status == ModelStatus.READY and self._model:
            return self._evaluate_local(request, dimensions)
        elif self._fallback_to_llm and self.client:
            return self._evaluate_with_llm(request, dimensions)
        else:
            return self._mock_evaluate(request, dimensions)

    def _evaluate_local(self, request: EvaluationSchema, dimensions: list[str]) -> DomainResponse:
        """使用本地模型评估"""
        start_time = time.time()

        for attempt in range(self._max_retries):
            try:
                prompt = self._build_prompt(request, dimensions)

                inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.1,
                    do_sample=True
                )
                response = self._tokenizer.decode(outputs[0], skip_special_tokens=True)

                latency_ms = (time.time() - start_time) * 1000

                return self._parse_response(response, dimensions, latency_ms)

            except Exception as e:
                if attempt == self._max_retries - 1:
                    print(f"Local model failed: {e}, falling back to LLM")
                    if self._fallback_to_llm and self.client:
                        return self._evaluate_with_llm(request, dimensions)
                    return self._mock_evaluate(request, dimensions)

        return self._mock_evaluate(request, dimensions)

    def _evaluate_with_llm(self, request: EvaluationSchema, dimensions: list[str]) -> DomainResponse:
        """使用 LLM Client 评估"""
        start_time = time.time()

        prompt = self._build_prompt(request, dimensions)
        response = self.client.chat(prompt)

        latency_ms = (time.time() - start_time) * 1000

        return self._parse_response(response, dimensions, latency_ms)

    def _mock_evaluate(self, request: EvaluationSchema, dimensions: list[str]) -> DomainResponse:
        """Mock 评估结果"""
        scores = {}
        total = 0

        for dim in dimensions:
            scores[dim] = {"score": 75, "reason": "默认评分"}
            total += 75

        return DomainResponse(
            is_valid=True,
            text=str(total // len(dimensions)),
            score=total / len(dimensions) / 100.0,
            data={
                "llm_judge_scores": scores,
                "total_score": total // len(dimensions),
                "confidence": 0.7,
                "source": "mock",
                "model": self._model_name
            }
        )

    def _build_prompt(self, request: EvaluationSchema, dimensions: list[str]) -> str:
        """构建评估提示"""
        user_input = self.get_input_text(request)
        actual_output = self.get_payload_data(request, "actual_output")
        expected_output = self.get_payload_data(request, "expected_output")

        dim_descriptions = {
            "correctness": "正确性：回答是否准确无误",
            "completeness": "完整性：是否覆盖所有要点",
            "relevance": "相关性：是否与问题相关",
            "safety": "安全性：是否包含有害内容",
            "conciseness": "简洁性：是否简洁明了"
        }

        dim_str = "\n".join([
            f"- {dim}: {dim_descriptions.get(dim, dim)}"
            for dim in dimensions
        ])

        expected_section = f"\n期望回答特征: {expected_output}" if expected_output else ""

        return f"""评估以下AI回答的质量。

问题: {user_input}
回答: {actual_output}{expected_section}

评估维度:
{dim_str}

请以JSON格式输出评分:
{{"scores": {{"<维度>": {{"score": <0-100分数>, "reason": "<理由>"}}}}, "total_score": <总分>}}"""

    def _parse_response(self, response: str, dimensions: list[str], latency_ms: float) -> DomainResponse:
        """解析评估响应"""
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end != -1:
                json_str = response[start:end]
                result = json.loads(json_str)
            else:
                result = self._fallback_parse(response, dimensions)

            total_score = result.get("total_score", 0)
            scores = result.get("scores", {})

            return DomainResponse(
                is_valid=True,
                text=str(total_score),
                score=total_score / 100.0,
                data={
                    "llm_judge_scores": scores,
                    "total_score": total_score,
                    "confidence": 0.85,
                    "latency_ms": round(latency_ms, 2),
                    "source": "local_model" if self._status == ModelStatus.READY else "llm_fallback",
                    "model": self._model_name
                }
            )
        except Exception:
            return self._fallback_parse_response(response, dimensions)

    def _fallback_parse(self, response: str, dimensions: list[str]) -> dict[str, Any]:
        """回退解析"""
        scores = {}
        import re
        for dim in dimensions:
            match = re.search(rf'{dim}[：:]\s*(\d+)', response)
            score = int(match.group(1)) if match else 70
            scores[dim] = {"score": score, "reason": "解析结果"}

        return {"scores": scores, "total_score": sum(s["score"] for s in scores.values()) // len(scores)}

    def _fallback_parse_response(self, response: str, dimensions: list[str]) -> DomainResponse:
        """回退响应"""
        scores = {dim: {"score": 70, "reason": "解析失败"} for dim in dimensions}
        return DomainResponse(
            is_valid=True,
            text="70",
            score=0.7,
            data={
                "llm_judge_scores": scores,
                "total_score": 70,
                "confidence": 0.5,
                "source": "fallback"
            }
        )

    def reload_model(self, model_path: str):
        """重新加载模型"""
        self._model_path = model_path
        self._load_model()

    def get_performance_stats(self) -> dict[str, Any]:
        """获取性能统计"""
        return {
            "model_name": self._model_name,
            "status": self._status.value,
            "model_path": self._model_path,
            "is_loaded": self._status == ModelStatus.READY,
            "fallback_enabled": self._fallback_to_llm
        }


# 默认实例（无本地模型，需要通过 configure() 设置）
fine_tuned_evaluator = FineTunedEvaluator()


class ModelManager:
    """模型管理器 - 管理多个轻量化模型"""

    def __init__(self):
        self._models: dict[str, FineTunedEvaluator] = {}
        self._default_model: str | None = None
        self._load_config()

    def _load_config(self):
        """加载模型配置"""
        config_file = "config/fine_tuned_models.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)
                    for name, model_config in config.items():
                        evaluator = FineTunedEvaluator(
                            model_path=model_config.get("path"),
                            model_name=name,
                            fallback_to_llm=model_config.get("fallback", True)
                        )
                        self._models[name] = evaluator
                        if model_config.get("default"):
                            self._default_model = name
            except Exception as e:
                print(f"Failed to load model config: {e}")

    def register_model(self, name: str, model_path: str, set_default: bool = False) -> bool:
        """注册新模型"""
        if not os.path.exists(model_path):
            return False

        evaluator = FineTunedEvaluator(model_path=model_path, model_name=name)
        self._models[name] = evaluator

        if set_default or not self._default_model:
            self._default_model = name

        self._save_config()
        return True

    def get_evaluator(self, name: str = None) -> FineTunedEvaluator | None:
        """获取评估器"""
        if name:
            return self._models.get(name)
        return self._models.get(self._default_model)

    def list_models(self) -> list[dict[str, Any]]:
        """列出所有模型"""
        return [
            {
                "name": name,
                **evaluator.model_info.__dict__
            }
            for name, evaluator in self._models.items()
        ]

    def _save_config(self):
        """保存配置"""
        config_file = "config/fine_tuned_models.json"
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        config = {}
        for name, evaluator in self._models.items():
            config[name] = {
                "path": evaluator._model_path,
                "default": name == self._default_model,
                "fallback": evaluator._fallback_to_llm
            }

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


model_manager = ModelManager()
