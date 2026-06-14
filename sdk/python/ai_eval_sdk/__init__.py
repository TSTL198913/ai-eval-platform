"""
AI Evaluation Platform SDK v1.0

提供简洁易用的 API，一行代码完成 AI 模型评测。

使用示例:
    from ai_eval_sdk import Client

    client = Client(api_key="your-api-key")

    # 单模型评测
    result = client.evaluate(
        model="gpt-4",
        dataset="mmlu",
        metrics=["accuracy", "latency"]
    )

    # 模型对比
    report = client.compare([
        {"model": "gpt-4", "dataset": "mmlu"},
        {"model": "claude-3", "dataset": "mmlu"}
    ])
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ClientConfig:
    """SDK 配置"""

    api_key: str
    base_url: str = "https://api.ai-eval.com"
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 0.5


@dataclass
class EvaluationRequest:
    """评测请求"""

    model: str
    dataset: str | None = None
    metrics: list[str] = field(default_factory=lambda: ["accuracy"])
    custom_prompts: list[str] | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """评测结果"""

    request_id: str
    model: str
    dataset: str
    metrics: dict[str, float]
    latency_ms: float
    timestamp: float
    status: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "model": self.model,
            "dataset": self.dataset,
            "metrics": self.metrics,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
            "status": self.status,
            "details": self.details,
        }

    def __str__(self) -> str:
        metrics_str = ", ".join(f"{k}={v:.2f}" for k, v in self.metrics.items())
        return f"EvaluationResult(model={self.model}, metrics={metrics_str}, latency={self.latency_ms:.1f}ms)"


@dataclass
class ComparisonReport:
    """对比报告"""

    report_id: str
    models: list[str]
    dataset: str
    results: list[EvaluationResult]
    rankings: dict[str, int]
    timestamp: float
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "models": self.models,
            "dataset": self.dataset,
            "results": [r.to_dict() for r in self.results],
            "rankings": self.rankings,
            "timestamp": self.timestamp,
            "summary": self.summary,
        }

    def print_summary(self):
        """打印对比摘要"""
        print("\n" + "=" * 60)
        print(f"Model Comparison Report - {self.dataset}")
        print("=" * 60)

        for model, rank in sorted(self.rankings.items(), key=lambda x: x[1]):
            result = next(r for r in self.results if r.model == model)
            metrics_str = ", ".join(f"{k}={v:.2f}" for k, v in result.metrics.items())
            print(f"#{rank} {model:20s} | {metrics_str} | {result.latency_ms:.1f}ms")

        print("=" * 60 + "\n")


class Client:
    """
    AI 评测平台客户端

    主要功能：
    - 单模型评测
    - 多模型对比
    - 异步评测
    - 结果查询
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.ai-eval.com",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        初始化客户端

        Args:
            api_key: API 密钥（可从环境变量 AI_EVAL_API_KEY 获取）
            base_url: API 地址
            timeout: 请求超时时间
            max_retries: 最大重试次数
        """
        self._config = ClientConfig(
            api_key=api_key or "",
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
        )
        logger.info(f"AI Eval SDK initialized: {base_url}")

    async def evaluate(
        self,
        model: str,
        dataset: str | None = None,
        metrics: list[str] | None = None,
        custom_prompts: list[str] | None = None,
        **kwargs,
    ) -> EvaluationResult:
        """
        评测单个模型

        Args:
            model: 模型名称（如 "gpt-4", "claude-3"）
            dataset: 数据集名称（如 "mmlu", "humaneval"）
            metrics: 评测指标（如 ["accuracy", "latency"]）
            custom_prompts: 自定义评测提示词
            **kwargs: 其他参数

        Returns:
            EvaluationResult: 评测结果

        Example:
            result = await client.evaluate(
                model="gpt-4",
                dataset="mmlu",
                metrics=["accuracy", "latency"]
            )
            print(result)
        """
        request = EvaluationRequest(
            model=model,
            dataset=dataset,
            metrics=metrics or ["accuracy"],
            custom_prompts=custom_prompts,
            parameters=kwargs,
        )

        response = await self._request_with_retry(
            "POST",
            "/v1/evaluate",
            json=request.__dict__,
        )

        return self._parse_result(response)

    async def evaluate_async(
        self,
        model: str,
        dataset: str | None = None,
        metrics: list[str] | None = None,
        **kwargs,
    ) -> str:
        """
        异步评测（提交任务）

        Args:
            model: 模型名称
            dataset: 数据集名称
            metrics: 评测指标

        Returns:
            str: 任务 ID

        Example:
            task_id = await client.evaluate_async(model="gpt-4", dataset="mmlu")
            result = await client.get_result(task_id)
        """
        request = EvaluationRequest(
            model=model,
            dataset=dataset,
            metrics=metrics or ["accuracy"],
            parameters=kwargs,
        )

        response = await self._request_with_retry(
            "POST",
            "/v1/evaluate/async",
            json=request.__dict__,
        )

        return response.get("task_id")

    async def get_result(self, task_id: str) -> EvaluationResult | None:
        """
        获取异步评测结果

        Args:
            task_id: 任务 ID

        Returns:
            EvaluationResult | None: 评测结果（如果已完成）
        """
        response = await self._request_with_retry(
            "GET",
            f"/v1/evaluate/result/{task_id}",
        )

        if response.get("status") == "completed":
            return self._parse_result(response)
        return None

    async def compare(
        self,
        models: list[dict[str, Any]],
        dataset: str | None = None,
        metrics: list[str] | None = None,
    ) -> ComparisonReport:
        """
        对比多个模型

        Args:
            models: 模型列表，如 [{"model": "gpt-4"}, {"model": "claude-3"}]
            dataset: 数据集名称
            metrics: 评测指标

        Returns:
            ComparisonReport: 对比报告

        Example:
            report = await client.compare([
                {"model": "gpt-4", "dataset": "mmlu"},
                {"model": "claude-3", "dataset": "mmlu"}
            ])
            report.print_summary()
        """
        request_data = {
            "models": models,
            "dataset": dataset,
            "metrics": metrics or ["accuracy"],
        }

        response = await self._request_with_retry(
            "POST",
            "/v1/compare",
            json=request_data,
        )

        return self._parse_comparison(response)

    async def list_datasets(self) -> list[dict]:
        """
        获取可用数据集列表

        Returns:
            list[dict]: 数据集列表
        """
        response = await self._request_with_retry("GET", "/v1/datasets")
        return response.get("datasets", [])

    async def list_models(self) -> list[dict]:
        """
        获取可用模型列表

        Returns:
            list[dict]: 模型列表
        """
        response = await self._request_with_retry("GET", "/v1/models")
        return response.get("models", [])

    async def get_usage(self) -> dict:
        """
        获取 API 使用统计

        Returns:
            dict: 使用统计
        """
        response = await self._request_with_retry("GET", "/v1/usage")
        return response

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict:
        """带重试的请求"""
        for attempt in range(self._config.max_retries):
            try:
                response = await self._client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self._config.max_retries - 1:
                    await asyncio.sleep(self._config.retry_delay * (attempt + 1))
                    continue
                raise
            except httpx.RequestError:
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(self._config.retry_delay * (attempt + 1))
                    continue
                raise

        raise Exception("Max retries exceeded")

    def _parse_result(self, data: dict) -> EvaluationResult:
        """解析评测结果"""
        return EvaluationResult(
            request_id=data.get("request_id", ""),
            model=data.get("model", ""),
            dataset=data.get("dataset", ""),
            metrics=data.get("metrics", {}),
            latency_ms=data.get("latency_ms", 0.0),
            timestamp=data.get("timestamp", time.time()),
            status=data.get("status", "completed"),
            details=data.get("details", {}),
        )

    def _parse_comparison(self, data: dict) -> ComparisonReport:
        """解析对比报告"""
        results = [self._parse_result(r) for r in data.get("results", [])]
        return ComparisonReport(
            report_id=data.get("report_id", ""),
            models=data.get("models", []),
            dataset=data.get("dataset", ""),
            results=results,
            rankings=data.get("rankings", {}),
            timestamp=data.get("timestamp", time.time()),
            summary=data.get("summary", {}),
        )

    async def close(self):
        """关闭客户端"""
        await self._client.aclose()
        logger.info("AI Eval SDK closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# 同步包装器（便于非异步环境使用）
class SyncClient:
    """
    同步客户端包装器

    用于不支持异步的环境。
    """

    def __init__(self, **kwargs):
        self._async_client = Client(**kwargs)

    def evaluate(self, **kwargs) -> EvaluationResult:
        """同步评测"""
        return asyncio.run(self._async_client.evaluate(**kwargs))

    def compare(self, **kwargs) -> ComparisonReport:
        """同步对比"""
        return asyncio.run(self._async_client.compare(**kwargs))

    def list_datasets(self) -> list[dict]:
        """获取数据集列表"""
        return asyncio.run(self._async_client.list_datasets())

    def list_models(self) -> list[dict]:
        """获取模型列表"""
        return asyncio.run(self._async_client.list_models())

    def close(self):
        """关闭客户端"""
        asyncio.run(self._async_client.close())


# 快捷函数
def evaluate(model: str, dataset: str, api_key: str | None = None) -> EvaluationResult:
    """
    快捷评测函数

    Example:
        result = evaluate("gpt-4", "mmlu", api_key="xxx")
        print(result)
    """
    client = SyncClient(api_key=api_key)
    result = client.evaluate(model=model, dataset=dataset)
    client.close()
    return result


def compare(models: list[dict], api_key: str | None = None) -> ComparisonReport:
    """
    快捷对比函数

    Example:
        report = compare([
            {"model": "gpt-4", "dataset": "mmlu"},
            {"model": "claude-3", "dataset": "mmlu"}
        ])
        report.print_summary()
    """
    client = SyncClient(api_key=api_key)
    report = client.compare(models=models)
    client.close()
    return report
