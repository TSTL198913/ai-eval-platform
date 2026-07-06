"""统一校准引擎（Unified Calibration Engine）

将 AdaptiveCalibrator 和 CalibrationManager 整合为单一校准引擎，
消除两套系统的状态不一致问题，提供统一的校准接口。

核心功能：
1. 统一的校准状态管理
2. 统一的触发机制（定时、漂移、Kappa下降、版本变更）
3. 统一的持久化机制
4. 统一的自愈能力
5. 统一的评估器校准检查
6. 事件驱动集成（通过EventBus发布校准事件）
"""

import logging
import threading
from datetime import datetime
from typing import Any
from typing import Optional

from src.domain.calibration.adaptive_calibrator import CalibrationResult
from src.domain.calibration.adaptive_calibrator import CalibrationStats
from src.domain.calibration.adaptive_calibrator import PreExecutionCheck
from src.domain.calibration.adaptive_calibrator import calibrator as adaptive_calibrator
from src.domain.evaluators.calibration_automation import CalibrationTrigger
from src.domain.evaluators.calibration_automation import calibration_manager as automation_manager
from src.infra.event_bus import EventType
from src.infra.event_bus import publish_event

logger = logging.getLogger(__name__)


class UnifiedCalibrationEngine:
    """统一校准引擎"""

    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._adaptive_calibrator = adaptive_calibrator
        self._automation_manager = automation_manager
        self._lock = threading.RLock()
        self._initialized = True
        logger.info("UnifiedCalibrationEngine 初始化完成")

    def record_evaluation(
        self,
        evaluator_type: str,
        result,
        expected_score: float,
    ):
        """记录评估结果用于校准"""
        self._adaptive_calibrator.record_evaluation(evaluator_type, result, expected_score)

    def apply_calibration(self, evaluator_type: str, score: float) -> float:
        """应用校准因子"""
        return self._adaptive_calibrator.apply_calibration(evaluator_type, score)

    def pre_execution_check(self, evaluator_name: str, dataset_id: str = None) -> PreExecutionCheck:
        """执行前校准检查"""
        return self._adaptive_calibrator.pre_execution_check(evaluator_name, dataset_id)

    def needs_calibration(
        self,
        evaluator_name: str,
        current_scores: list[float] | None = None,
        new_kappa: float | None = None,
        rubric_version: str | None = None,
        model_version: str | None = None,
    ) -> tuple[bool, CalibrationTrigger | None]:
        """检查是否需要校准

        优先使用自动化管理器的触发器检测，同时同步自适应校准器的状态。
        """
        if current_scores is None:
            stats = self._adaptive_calibrator.get_evaluator_stats(evaluator_name)
            if stats and stats.count >= 5:
                current_scores = stats.scores[-10:]

        needs_calib, trigger = self._automation_manager.needs_calibration(
            current_scores=current_scores,
            new_kappa=new_kappa,
            rubric_version=rubric_version,
            model_version=model_version,
        )

        if needs_calib:
            logger.info(f"统一校准引擎检测到需要校准 | evaluator={evaluator_name} | trigger={trigger.value}")
            publish_event(
                EventType.CALIBRATION_NEEDED,
                evaluator_name=evaluator_name,
                trigger=trigger.value if trigger else None,
                current_scores=current_scores,
                new_kappa=new_kappa,
                rubric_version=rubric_version,
                model_version=model_version,
                source="unified_calibration_engine",
            )

        return needs_calib, trigger

    def run_calibration(
        self,
        evaluator_name: str,
        evaluator,
        trigger: CalibrationTrigger,
        dataset_id: str = None,
    ) -> CalibrationResult | dict:
        """执行校准流程

        统一调用自适应校准器的黄金数据集校准和自动化管理器的校准流程。
        """
        try:
            result = self._adaptive_calibrator.run_golden_calibration(
                evaluator_name=evaluator_name,
                evaluator_func=lambda sample: evaluator.safe_evaluate(sample.input_data).__dict__,
                dataset_id=dataset_id or evaluator_name,
            )

            self._automation_manager.last_calibration_time = datetime.now()

            logger.info(
                f"统一校准引擎校准完成 | evaluator={evaluator_name} | "
                f"deviation={result.mean_deviation:.4f} | kappa={result.correlation:.4f} | "
                f"trigger={trigger.value}"
            )

            publish_event(
                EventType.SCORE_CALIBRATED,
                evaluator_name=evaluator_name,
                mean_deviation=result.mean_deviation,
                correlation=result.correlation,
                trigger=trigger.value,
                source="unified_calibration_engine",
            )

            return result
        except Exception as e:
            logger.error(f"统一校准引擎校准失败: {e}")
            publish_event(
                EventType.ERROR_OCCURRED,
                error_type="calibration_failed",
                evaluator_name=evaluator_name,
                error_message=str(e),
                source="unified_calibration_engine",
            )
            return {
                "success": False,
                "error": str(e),
                "evaluator_name": evaluator_name,
            }

    def detect_drift(self, evaluator_name: str, current_scores: list[float]) -> bool:
        """检测评分漂移"""
        is_drifted = self._adaptive_calibrator.detect_drift(evaluator_name, current_scores)
        if is_drifted:
            stats = self._adaptive_calibrator.get_evaluator_stats(evaluator_name)
            publish_event(
                EventType.DRIFT_DETECTED,
                evaluator_name=evaluator_name,
                current_scores=current_scores,
                historical_mean=stats.mean if stats else None,
                source="unified_calibration_engine",
            )
        return is_drifted

    def check_kappa_degradation(self, evaluator_name: str, new_kappa: float) -> bool:
        """检查Kappa值是否下降"""
        return self._adaptive_calibrator.check_kappa_degradation(evaluator_name, new_kappa)

    def check_sla_compliance(self, evaluator_name: str) -> dict[str, bool]:
        """检查SLA合规性"""
        return self._adaptive_calibrator.check_sla_compliance(evaluator_name)

    def get_sla_metrics(self, evaluator_name: str) -> dict[str, Any]:
        """获取SLA指标"""
        return self._adaptive_calibrator.get_sla_metrics(evaluator_name)

    def get_calibration_report(self, evaluator_name: str) -> dict[str, Any]:
        """获取校准报告"""
        report = self._adaptive_calibrator.get_golden_calibration_report(evaluator_name)
        report.update(self._automation_manager.get_calibration_report())
        return report

    def get_all_alerts(self, resolved: bool = False) -> list:
        """获取所有警报"""
        return self._adaptive_calibrator.get_all_alerts(resolved)

    def get_evaluator_stats(self, evaluator_type: str) -> Optional[CalibrationStats]:
        """获取评估器统计信息"""
        return self._adaptive_calibrator.get_evaluator_stats(evaluator_type)

    def trigger_recalibration(self, evaluator_name: str):
        """触发自动重校准

        Args:
            evaluator_name: 评估器名称

        Returns:
            CalibrationResult | dict: 校准结果
        """
        logger.warning(f"[自动重校准] 触发 | evaluator={evaluator_name}")

        needs_calib, trigger = self.needs_calibration(evaluator_name)
        if not needs_calib:
            logger.info(f"[自动重校准] 评估器不需要校准 | evaluator={evaluator_name}")
            return {"success": True, "message": "No calibration needed"}

        try:
            from src.domain.evaluators.evaluator_factory import EvaluatorFactory
            from src.domain.model_routing import model_router

            llm_client, routing_decision = model_router.create_llm_client(
                task_type=evaluator_name
            )
            logger.info(f"[自动重校准] 获取LLM客户端 | provider={routing_decision['provider']} | model={routing_decision['model_name']}")

            evaluator = EvaluatorFactory.get(evaluator_name, client=llm_client)
            if evaluator is None:
                logger.error(f"[自动重校准] 评估器不存在 | evaluator={evaluator_name}")
                return {"success": False, "error": f"Evaluator {evaluator_name} not found"}

            result = self.run_calibration(
                evaluator_name=evaluator_name,
                evaluator=evaluator,
                trigger=trigger,
            )

            logger.info(f"[自动重校准] 完成 | evaluator={evaluator_name}")
            return result
        except Exception as e:
            logger.error(f"[自动重校准] 失败 | evaluator={evaluator_name} | error={e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def save_state(self):
        """保存校准状态"""
        self._adaptive_calibrator._save_state_to_redis()

    def load_state(self):
        """加载校准状态"""
        self._adaptive_calibrator._load_state_from_redis()

    def reset(self):
        """重置校准器状态"""
        self._adaptive_calibrator.reset()
        self._automation_manager.calibration_history.clear()
        self._automation_manager.last_calibration_time = None
        logger.info("UnifiedCalibrationEngine 已重置")

    @classmethod
    def get_instance(cls) -> "UnifiedCalibrationEngine":
        """获取单例实例"""
        return cls()


calibration_engine = UnifiedCalibrationEngine()