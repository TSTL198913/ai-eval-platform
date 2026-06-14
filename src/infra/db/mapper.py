# src/infra/mapper.py
from typing import Any


class EvaluationMapper:
    @staticmethod
    def to_persistence_dict(result_model: Any, case_id: str) -> dict[str, Any]:
        """
        职责：将评测结果转换为持久层格式，处理所有的数据对齐与字段补全。
        """
        # 1. 提取原始数据
        data = (
            result_model.model_dump() if hasattr(result_model, "model_dump") else dict(result_model)
        )

        # 2. 强制契约补全：确保 case_id 永远存在
        # 使用 setdefault 或直接赋值，确保下游持久化层不会因缺少字段报错
        data["case_id"] = case_id or "unknown_case_id"

        # 3. 可以在此添加其他统一处理，比如日期格式化、敏感字段过滤等
        # data["processed_at"] = datetime.utcnow().isoformat()

        return data
