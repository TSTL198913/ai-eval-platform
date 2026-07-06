"""
事件订阅者（Event Subscribers）

实现智能自动化闭环：
- CALIBRATION_NEEDED → 自动校准调度
- EVALUATION_COMPLETED → 评估统计收集
- DRIFT_DETECTED → 自动触发重校准
- FALLBACK_TRIGGERED → 自动熔断/告警
- ERROR_OCCURRED → 错误告警与统计
- SCORE_CALIBRATED → 持久化校准历史
- SELF_HEALING_STARTED → 自修复开始记录
- SELF_HEALING_COMPLETED → 自修复结果验证
"""

import logging
import time

from src.infra.event_bus import Event
from src.infra.event_bus import EventType
from src.infra.event_bus import subscribe_event

logger = logging.getLogger(__name__)

_evaluation_stats = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "by_evaluator": {},
    "start_time": time.time(),
}


def handle_calibration_needed(event: Event):
    """
    处理校准需求事件：自动调度校准任务

    Args:
        event: 校准需求事件，包含 evaluator_name、reason、priority 等
    """
    payload = event.payload
    evaluator_name = payload.get("evaluator_name")
    reason = payload.get("reason", "unknown")
    priority = payload.get("priority", "normal")

    logger.info(
        f"[智能自动化] 收到校准需求 | evaluator={evaluator_name} | "
        f"reason={reason} | priority={priority}"
    )

    try:
        from src.domain.calibration.unified_calibration_engine import UnifiedCalibrationEngine

        engine = UnifiedCalibrationEngine()
        result = engine.trigger_recalibration(evaluator_name, reason=reason)
        logger.info(
            f"[智能自动化] 校准需求已处理 | evaluator={evaluator_name} | "
            f"result={'success' if result else 'failed'}"
        )
    except Exception as e:
        logger.error(
            f"[智能自动化] 自动校准调度失败 | evaluator={evaluator_name} | error={e}",
            exc_info=True,
        )


def handle_evaluation_completed(event: Event):
    """
    处理评估完成事件：收集评估统计数据

    Args:
        event: 评估完成事件，包含 evaluator_type、score、status、duration 等
    """
    payload = event.payload
    evaluator_type = payload.get("evaluator_type", "unknown")
    status = payload.get("status", "unknown")
    duration = payload.get("duration_ms", 0)

    _evaluation_stats["total"] += 1

    if status in ("success", "SUCCESS", "partial", "PARTIAL"):
        _evaluation_stats["success"] += 1
    else:
        _evaluation_stats["failed"] += 1

    if evaluator_type not in _evaluation_stats["by_evaluator"]:
        _evaluation_stats["by_evaluator"][evaluator_type] = {"total": 0, "success": 0, "failed": 0}
    eval_stats = _evaluation_stats["by_evaluator"][evaluator_type]
    eval_stats["total"] += 1
    if status in ("success", "SUCCESS", "partial", "PARTIAL"):
        eval_stats["success"] += 1
    else:
        eval_stats["failed"] += 1

    if _evaluation_stats["total"] % 100 == 0:
        elapsed = time.time() - _evaluation_stats["start_time"]
        rate = _evaluation_stats["total"] / max(elapsed, 1) * 60
        success_rate = _evaluation_stats["success"] / max(_evaluation_stats["total"], 1) * 100
        logger.info(
            f"[智能自动化] 评估统计 | total={_evaluation_stats['total']} | "
            f"success_rate={success_rate:.1f}% | rate={rate:.1f}/min"
        )


def handle_error_occurred(event: Event):
    """
    处理错误事件：错误告警与统计

    Args:
        event: 错误事件，包含 error_type、error_message、evaluator_name、source 等
    """
    payload = event.payload
    error_type = payload.get("error_type", "unknown")
    error_message = payload.get("error_message", "")
    evaluator_name = payload.get("evaluator_name", "unknown")
    source = payload.get("source", event.source)

    logger.error(
        f"[智能自动化] 错误告警 | type={error_type} | evaluator={evaluator_name} | "
        f"source={source} | message={error_message[:200]}"
    )

    try:
        from src.distributed.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry.get_instance()
        cb = registry.get_or_create(f"error_{error_type}")
        cb.record_failure()

        if cb.is_open:
            logger.critical(
                f"[智能自动化] 错误率过高，熔断器触发 | type={error_type} | "
                f"evaluator={evaluator_name} | failure_count={cb.failure_count}"
            )
    except Exception as e:
        logger.warning(
            f"[智能自动化] 错误统计熔断器更新失败 | error={e}",
            exc_info=True,
        )


def handle_self_healing_started(event: Event):
    """
    处理自修复开始事件：记录自修复启动

    Args:
        event: 自修复开始事件，包含 evaluator_name、reason、healing_method 等
    """
    payload = event.payload
    evaluator_name = payload.get("evaluator_name")
    reason = payload.get("reason", "unknown")
    healing_method = payload.get("healing_method", "unknown")

    logger.warning(
        f"[智能自动化] 自修复启动 | evaluator={evaluator_name} | "
        f"reason={reason} | method={healing_method}"
    )


def handle_self_healing_completed(event: Event):
    """
    处理自修复完成事件：验证修复效果，失败则升级告警

    Args:
        event: 自修复完成事件，包含 evaluator_name、success、before_score、after_score、improvement 等
    """
    payload = event.payload
    evaluator_name = payload.get("evaluator_name")
    success = payload.get("success", False)
    before_deviation = payload.get("before_deviation")
    after_deviation = payload.get("after_deviation")
    improvement = payload.get("improvement")

    if success:
        if improvement is not None and improvement > 0:
            logger.info(
                f"[智能自动化] 自修复成功 | evaluator={evaluator_name} | "
                f"before={before_deviation} | after={after_deviation} | "
                f"improvement={improvement:.2%}"
            )
        else:
            logger.warning(
                f"[智能自动化] 自修复完成但无改善 | evaluator={evaluator_name} | "
                f"before={before_deviation} | after={after_deviation}"
            )
    else:
        logger.error(
            f"[智能自动化] 自修复失败，需要人工干预 | evaluator={evaluator_name} | "
            f"reason={payload.get('failure_reason', 'unknown')}"
        )


def handle_drift_detected(event: Event):
    """
    处理漂移检测事件：自动触发重校准

    Args:
        event: 漂移检测事件，包含 evaluator_name、current_scores、historical_mean 等
    """
    payload = event.payload
    evaluator_name = payload.get("evaluator_name")
    current_scores = payload.get("current_scores", [])
    historical_mean = payload.get("historical_mean")

    logger.warning(
        f"[智能自动化] 检测到漂移 | evaluator={evaluator_name} | "
        f"current_scores={current_scores[:5]}... | historical_mean={historical_mean}"
    )

    try:
        from src.domain.calibration.unified_calibration_engine import UnifiedCalibrationEngine

        engine = UnifiedCalibrationEngine()
        engine.trigger_recalibration(evaluator_name)
        logger.info(f"[智能自动化] 已自动触发重校准 | evaluator={evaluator_name}")
    except Exception as e:
        logger.error(
            f"[智能自动化] 自动重校准失败 | evaluator={evaluator_name} | error={e}",
            exc_info=True,
        )


def handle_fallback_triggered(event: Event):
    """
    处理降级触发事件：自动熔断/告警

    Args:
        event: 降级触发事件，包含 fallback_method、score、confidence、error_message 等
    """
    payload = event.payload
    fallback_method = payload.get("fallback_method")
    score = payload.get("score")
    confidence = payload.get("confidence")
    error_message = payload.get("error_message")

    logger.warning(
        f"[智能自动化] 降级触发 | method={fallback_method} | "
        f"score={score} | confidence={confidence} | error={error_message}"
    )

    try:
        from src.distributed.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry.get_instance()
        cb = registry.get_or_create("evaluator_fallback")
        cb.record_failure()

        if cb.is_open:
            logger.error(
                f"[智能自动化] 熔断器已打开 | method={fallback_method} | "
                f"failure_count={cb.failure_count} | threshold={cb.failure_threshold}"
            )
    except Exception as e:
        logger.error(
            f"[智能自动化] 熔断处理失败 | method={fallback_method} | error={e}",
            exc_info=True,
        )


def handle_score_calibrated(event: Event):
    """
    处理分数校准完成事件：持久化校准历史

    Args:
        event: 分数校准事件，包含 evaluator_name、calibration_factor、confidence 等
    """
    payload = event.payload
    evaluator_name = payload.get("evaluator_name")
    calibration_factor = payload.get("calibration_factor")
    confidence = payload.get("confidence")

    logger.info(
        f"[智能自动化] 分数校准完成 | evaluator={evaluator_name} | "
        f"calibration_factor={calibration_factor} | confidence={confidence}"
    )

    try:
        from src.domain.services.persistence_service import PersistenceService

        persistence = PersistenceService()
        persistence.save_calibration_history(
            evaluator_name=evaluator_name,
            calibration_factor=calibration_factor,
            confidence=confidence,
            source=event.source,
        )
        logger.info(
            f"[智能自动化] 校准历史已持久化 | evaluator={evaluator_name}"
        )
    except Exception as e:
        logger.error(
            f"[智能自动化] 校准历史持久化失败 | evaluator={evaluator_name} | error={e}",
            exc_info=True,
        )


def initialize_subscribers():
    """
    初始化所有事件订阅者

    建立智能自动化闭环（8个事件全覆盖）：
    - CALIBRATION_NEEDED → 自动校准调度
    - EVALUATION_COMPLETED → 评估统计收集
    - DRIFT_DETECTED → 自动重校准
    - FALLBACK_TRIGGERED → 自动熔断/告警
    - ERROR_OCCURRED → 错误告警与统计
    - SCORE_CALIBRATED → 持久化校准历史
    - SELF_HEALING_STARTED → 自修复开始记录
    - SELF_HEALING_COMPLETED → 自修复结果验证
    """
    subscribe_event(EventType.CALIBRATION_NEEDED, handle_calibration_needed)
    subscribe_event(EventType.EVALUATION_COMPLETED, handle_evaluation_completed)
    subscribe_event(EventType.DRIFT_DETECTED, handle_drift_detected)
    subscribe_event(EventType.FALLBACK_TRIGGERED, handle_fallback_triggered)
    subscribe_event(EventType.ERROR_OCCURRED, handle_error_occurred)
    subscribe_event(EventType.SCORE_CALIBRATED, handle_score_calibrated)
    subscribe_event(EventType.SELF_HEALING_STARTED, handle_self_healing_started)
    subscribe_event(EventType.SELF_HEALING_COMPLETED, handle_self_healing_completed)

    logger.info("事件订阅者初始化完成 (8/8 事件已订阅)")