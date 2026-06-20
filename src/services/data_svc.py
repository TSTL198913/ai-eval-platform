import logging
from typing import Any, Dict, List, Optional

from src.infra.db.repository import EvaluationRepository
from src.schemas.evaluation import EvaluationConfig


class EvaluationDataService:
    def __init__(self):
        self._repository = EvaluationRepository()

    def count(self) -> int:
        return self._repository.count()

    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._repository.get_recent(limit=limit)

    def search(self, evaluator=None, status=None, limit=10, type=None, offset=0, sort_by="created_at", sort_order="desc"):
        return self._repository.search(evaluator=evaluator, status=status, limit=limit, type=type, offset=offset, sort_by=sort_by, sort_order=sort_order)

    def get_all_for_export(self) -> List[Dict[str, Any]]:
        return self._repository.get_all_for_export()

    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        return self._repository.get_by_id(record_id)

    def update(self, record_id: int, update_data: Dict[str, Any]) -> bool:
        return self._repository.update(record_id, update_data)

    def delete(self, record_id: int) -> bool:
        return self._repository.delete(record_id)

    def batch_delete(self, record_ids: List[int]) -> int:
        return self._repository.batch_delete(record_ids)

    def batch_update(self, record_ids: List[int], update_data: Dict[str, Any]) -> int:
        return self._repository.batch_update(record_ids, update_data)

    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._repository.get_all(limit=limit)

    def save_config(self, config):
        return self._repository.save_config(config)

    def get_by_case_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        records = self._repository.search(type=case_id, limit=100)
        for record in records:
            if record.get('case_id') == case_id:
                return record
        return None

    def delete_by_case_id(self, case_id: str) -> int:
        records = self._repository.search(type=case_id, limit=100)
        deleted_count = 0
        for record in records:
            if record.get('case_id') == case_id:
                if self._repository.delete(record['id']):
                    deleted_count += 1
        return deleted_count


_data_service = None

def get_data_service():
    global _data_service
    if _data_service is None:
        _data_service = EvaluationDataService()
    return _data_service
