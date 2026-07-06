import logging
from typing import Optional

from src.infra.db.repository import EvaluationRepository
from src.schemas.schemas import EvaluationResult

logger = logging.getLogger(__name__)


class PersistenceService:
    """独立持久化服务：负责评估结果的持久化
    
    职责：
    - 将评估结果保存到数据库
    - 提供持久化状态的统一管理
    - 隔离业务逻辑与数据访问层
    """

    def __init__(self, repository: Optional[EvaluationRepository] = None):
        self.repository = repository or EvaluationRepository()

    def save_evaluation(self, result: EvaluationResult) -> dict[str, bool | str | int]:
        """保存评估结果
        
        Args:
            result: 评估结果对象
            
        Returns:
            dict: 持久化状态信息
                - success: 是否成功
                - db_id: 数据库ID（成功时）
                - error: 错误信息（失败时）
        """
        try:
            db_id = self.repository.save(result)
            logger.info(
                f"评估结果已持久化: id={db_id}, case_id={result.case_id}, status={result.status.value}"
            )
            return {"success": True, "db_id": db_id, "error": None}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"评估结果持久化失败: {e}", exc_info=True)
            return {"success": False, "db_id": None, "error": error_msg}

    def save_calibration_history(
        self,
        evaluator_name: str,
        calibration_factor: float = None,
        confidence: float = None,
        source: str = None,
        **kwargs,
    ) -> dict[str, bool | str]:
        """保存校准历史记录
        
        Args:
            evaluator_name: 评估器名称
            calibration_factor: 校准因子
            confidence: 置信度
            source: 校准来源
            **kwargs: 额外的校准数据
            
        Returns:
            dict: 持久化状态信息
                - success: 是否成功
                - error: 错误信息（失败时）
        """
        try:
            from src.infra.db.models import CalibrationHistoryModel
            from src.infra.db.session import get_db

            db = next(get_db())
            history_record = CalibrationHistoryModel(
                evaluator_name=evaluator_name,
                calibration_factor=calibration_factor,
                confidence=confidence,
                source=source,
                metadata=kwargs,
            )
            db.add(history_record)
            db.commit()
            db.refresh(history_record)

            logger.info(
                f"校准历史已持久化 | evaluator={evaluator_name} | "
                f"factor={calibration_factor} | confidence={confidence}"
            )
            return {"success": True, "error": None}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"校准历史持久化失败: {e}", exc_info=True)
            return {"success": False, "error": error_msg}