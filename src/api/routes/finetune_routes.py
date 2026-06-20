"""
微调路由模块
包含训练数据导出、模型管理、评估等端点
"""

import logging
import time

from fastapi import APIRouter

from src.api.common import error_response, success_response
from src.schemas.evaluation import EvaluationSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/finetune", tags=["微调"])


@router.get("/export/datasets")
async def list_exportable_datasets():
    """列出可导出的黄金数据集"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager

        datasets = golden_dataset_manager.list_datasets()
        exportable = []

        for ds in datasets:
            if ds.samples:
                stats = {
                    "total_samples": len(ds.samples),
                    "corrected_samples": sum(1 for s in ds.samples if s.human_corrected),
                    "avg_score": (
                        sum(s.scores.values() for s in ds.samples) / max(len(ds.samples), 1)
                        if ds.samples
                        else 0
                    ),
                }
                exportable.append(
                    {
                        "id": ds.id,
                        "name": ds.name,
                        "description": ds.description,
                        "samples_count": len(ds.samples),
                        "corrected_count": stats["corrected_samples"],
                        "avg_score": round(stats["avg_score"], 1),
                        "exportable": stats["corrected_samples"] >= 50,
                    }
                )

        return success_response({"datasets": exportable})
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        return error_response(500, "获取数据集列表失败")


@router.post("/export")
async def export_training_data(data: dict):
    """导出训练数据"""
    try:
        from src.domain.fine_tune_exporter import ExportFormat, fine_tune_exporter

        dataset_id = data.get("dataset_id")
        output_dir = data.get("output_dir", "data/fine_tune")
        format_str = data.get("format", "openai")
        min_score = data.get("min_score", 0.0)

        if not dataset_id:
            return error_response(400, "dataset_id 必填")

        export_format = ExportFormat(format_str)
        filepath = fine_tune_exporter.export_from_golden_dataset(
            dataset_id=dataset_id, output_dir=output_dir, format=export_format, min_score=min_score
        )

        stats = fine_tune_exporter.get_stats()

        return success_response({"message": "导出成功", "file_path": filepath, "stats": stats})
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        logger.error(f"Failed to export: {e}")
        return error_response(500, "导出失败")


@router.post("/export/db")
async def export_from_database(data: dict = None):
    """从数据库导出训练数据"""
    try:
        from src.domain.fine_tune_exporter import ExportFormat, fine_tune_exporter

        data = data or {}
        output_dir = data.get("output_dir", "data/fine_tune")
        format_str = data.get("format", "openai")
        limit = data.get("limit", 1000)
        min_score = data.get("min_score", 50.0)

        export_format = ExportFormat(format_str)
        filepath = fine_tune_exporter.export_from_db(
            output_dir=output_dir, format=export_format, limit=limit, min_score=min_score
        )

        stats = fine_tune_exporter.get_stats()

        return success_response(
            {"message": "数据库导出成功", "file_path": filepath, "stats": stats}
        )
    except Exception as e:
        logger.error(f"Failed to export from DB: {e}")
        return error_response(500, "数据库导出失败")


@router.get("/quality-report")
async def get_quality_report(dataset_id: str = None):
    """获取训练数据质量报告"""
    try:
        from src.domain.fine_tune_exporter import fine_tune_exporter
        from src.domain.golden_dataset import golden_dataset_manager

        if dataset_id:
            dataset = golden_dataset_manager.get_dataset(dataset_id)
            if not dataset:
                return error_response(404, f"Dataset '{dataset_id}' not found")

            samples = [
                {
                    "id": s.id,
                    "metadata": {
                        "avg_score": (
                            sum(s.scores.values()) / max(len(s.scores), 1) if s.scores else 0
                        )
                    },
                }
                for s in dataset.samples
            ]
        else:
            datasets = golden_dataset_manager.list_datasets()
            samples = [
                {
                    "id": s.id,
                    "metadata": {
                        "avg_score": (
                            sum(s.scores.values()) / max(len(s.scores), 1) if s.scores else 0
                        )
                    },
                }
                for ds in datasets
                for s in ds.samples
            ]

        # 转换为 TrainingSample 格式用于分析
        training_samples = []
        for s in samples:
            training_samples.append(
                type("Sample", (), {"id": s["id"], "metadata": s["metadata"]})()
            )

        report = fine_tune_exporter.generate_quality_report(training_samples)

        return success_response(report)
    except Exception as e:
        logger.error(f"Failed to generate quality report: {e}")
        return error_response(500, "生成质量报告失败")


@router.get("/models")
async def list_fine_tuned_models():
    """列出已注册的 Fine-tuned 模型"""
    try:
        from src.domain.fine_tuned_evaluator import model_manager

        models = model_manager.list_models()

        return success_response({"models": models, "default_model": model_manager._default_model})
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return error_response(500, "获取模型列表失败")


@router.post("/models")
async def register_fine_tuned_model(data: dict):
    """注册新的 Fine-tuned 模型"""
    try:
        from src.domain.fine_tuned_evaluator import model_manager

        name = data.get("name")
        model_path = data.get("model_path")
        set_default = data.get("set_default", False)

        if not name or not model_path:
            return error_response(400, "name 和 model_path 必填")

        success = model_manager.register_model(name, model_path, set_default)

        if success:
            return success_response(
                {"message": "模型注册成功", "name": name, "model_path": model_path}
            )
        else:
            return error_response(400, f"模型路径不存在: {model_path}")
    except Exception as e:
        logger.error(f"Failed to register model: {e}")
        return error_response(500, "注册模型失败")


@router.post("/evaluate")
async def evaluate_with_fine_tuned(data: dict):
    """使用 Fine-tuned 模型进行评估"""
    try:
        from src.domain.fine_tuned_evaluator import model_manager

        model_name = data.get("model_name")
        user_input = data.get("user_input")
        actual_output = data.get("actual_output")
        dimensions = data.get("dimensions", ["correctness"])

        if not user_input or not actual_output:
            return error_response(400, "user_input 和 actual_output 必填")

        evaluator = model_manager.get_evaluator(model_name)

        if not evaluator:
            return error_response(404, f"模型 '{model_name}' 未找到")

        request = EvaluationSchema(
            id=f"finetune_eval_{int(time.time())}",
            type="fine_tuned",
            payload={
                "user_input": user_input,
                "actual_output": actual_output,
                "dimensions": dimensions,
            },
        )

        result = evaluator.evaluate(request)

        return success_response(
            {"result": result.data, "model_status": evaluator.model_info.status.value}
        )
    except Exception as e:
        logger.error(f"Failed to evaluate: {e}")
        return error_response(500, "评估失败")


@router.get("/guide")
async def get_fine_tune_guide():
    """获取 Fine-tune 操作指南"""
    guide = {
        "title": "Fine-tune 操作指南",
        "steps": [
            {
                "step": 1,
                "title": "积累高质量样本",
                "description": "通过黄金数据集积累至少 200+ 修正后的样本",
                "api": "POST /api/v1/calibration/datasets/{id}/samples/{sample_id}/correct",
            },
            {
                "step": 2,
                "title": "导出训练数据",
                "description": "导出为 OpenAI 或 LLaMA-Factory 格式",
                "api": "POST /api/v1/finetune/export",
            },
            {
                "step": 3,
                "title": "数据质量检查",
                "description": "检查导出数据的质量评分和分布",
                "api": "GET /api/v1/finetune/quality-report",
            },
            {
                "step": 4,
                "title": "本地 Fine-tune",
                "description": "使用 LLaMA-Factory 或 OpenAI Fine-tune API 训练",
                "command": "llamafactory-cli train examples/train_lora/eval_judge.yaml",
            },
            {
                "step": 5,
                "title": "注册模型",
                "description": "将训练好的模型注册到评估系统",
                "api": "POST /api/v1/finetune/models",
            },
            {
                "step": 6,
                "title": "对比测试",
                "description": "对比 Fine-tuned 模型与原 GPT-4 的效果和延迟",
                "api": "POST /api/v1/finetune/evaluate",
            },
        ],
        "recommended_models": [
            {"name": "Qwen2-0.5B", "size": "500MB", "use_case": "快速评估"},
            {"name": "Phi-3-mini", "size": "2.3GB", "use_case": "高质量评估"},
            {"name": "DeepSeek-1.5B", "size": "1.5GB", "use_case": "中文优化"},
        ],
        "expected_improvement": {
            "token_cost": "降低 70-95%",
            "latency": "提升 5-20倍",
            "accuracy": "领域任务提升 10-30%",
        },
    }
    return success_response(guide)
