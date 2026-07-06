from loguru import logger

from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema


class CalibrationMixin:
    _self_healing_failure_counts: dict = {}

    def _record_for_calibration(
        self, evaluator_type: str, response: DomainResponse, request: EvaluationSchema
    ) -> None:
        try:
            from src.domain.calibration.unified_calibration_engine import calibration_engine

            expected_score = request.metadata.get("golden_score") if request.metadata else None
            if expected_score is None:
                return

            expected_score = float(expected_score)
            calibration_engine.record_evaluation(evaluator_type, response, expected_score)
        except Exception as e:
            logger.debug(f"校准记录失败: {e}")

    def _trigger_auto_calibration(self, evaluator_name: str, response: DomainResponse) -> None:
        try:
            from src.domain.calibration.unified_calibration_engine import calibration_engine

            stats = calibration_engine.get_evaluator_stats(evaluator_name)
            if stats and stats.count >= 10:
                current_scores = stats.scores[-10:]

                needs_calib, trigger = calibration_engine.needs_calibration(
                    evaluator_name=evaluator_name,
                    current_scores=current_scores,
                )

                if needs_calib:
                    logger.info(f"自动校准触发 | evaluator={evaluator_name} | trigger={trigger.value}")
                    self._start_async_calibration(evaluator_name, trigger)
        except Exception as e:
            logger.debug(f"自动校准触发失败: {e}")

    def _start_async_calibration(self, evaluator_name: str, trigger) -> None:
        try:
            import threading

            from src.domain.golden_dataset import golden_dataset_manager

            dataset = golden_dataset_manager.get_dataset_by_category(evaluator_name)
            if not dataset:
                return

            golden_data = []
            for sample in dataset.samples[:20]:
                if sample.scores:
                    expert_score = sum(sample.scores.values()) / len(sample.scores)
                    golden_data.append({
                        "request": sample.input_data,
                        "expert_score": expert_score,
                    })

            def run_calibration_task():
                from src.domain.evaluators.calibration_automation import calibration_manager
                try:
                    result = calibration_manager.run_calibration(
                        trigger=trigger,
                        evaluator=self,
                        golden_dataset=golden_data,
                    )
                    if result.success:
                        logger.info(f"异步校准成功 | evaluator={evaluator_name} | deviation={result.deviation:.4f}")
                    else:
                        logger.warning(f"异步校准失败 | evaluator={evaluator_name} | deviation={result.deviation:.4f}")
                except Exception as e:
                    logger.error(f"异步校准任务失败: {e}")

            thread = threading.Thread(target=run_calibration_task, daemon=True)
            thread.start()
        except Exception as e:
            logger.error(f"启动异步校准任务失败: {e}")

    def _start_self_healing(self, evaluator_name: str) -> None:
        try:
            import threading
            import time

            failure_count = self._self_healing_failure_counts.get(evaluator_name, 0)
            if failure_count >= 3:
                logger.error(
                    f"自愈已连续失败 {failure_count} 次，停止自动修复 | "
                    f"evaluator={evaluator_name} | 需要人工干预"
                )
                try:
                    from src.infra.event_bus import EventBus, EventType
                    bus = EventBus()
                    bus.publish(
                        EventType.ERROR_OCCURRED,
                        error_type="self_healing_escalation",
                        error_message=f"评估器 {evaluator_name} 自愈连续失败 {failure_count} 次，需要人工干预",
                        evaluator_name=evaluator_name,
                        source="calibration_mixin",
                    )
                except Exception:
                    pass
                return

            logger.info(f"启动自愈流程 | evaluator={evaluator_name} | 当前失败次数={failure_count}")

            def self_healing_task():
                try:
                    time.sleep(5)

                    from src.domain.evaluators.calibration_automation import CalibrationTrigger
                    from src.domain.evaluators.calibration_automation import calibration_manager
                    from src.domain.golden_dataset import golden_dataset_manager
                    from src.infra.event_bus import EventBus, Event, EventType

                    bus = EventBus()

                    bus.publish(Event(
                        event_type=EventType.SELF_HEALING_STARTED,
                        payload={
                            "evaluator_name": evaluator_name,
                            "reason": "calibration_gate_failed",
                            "healing_method": "recalibration",
                        },
                        source="calibration_mixin",
                    ))

                    dataset = golden_dataset_manager.get_dataset_by_category(evaluator_name)
                    if not dataset:
                        logger.warning(f"自愈失败: 评估器 {evaluator_name} 没有黄金数据集")
                        bus.publish(Event(
                            event_type=EventType.SELF_HEALING_COMPLETED,
                            payload={
                                "evaluator_name": evaluator_name,
                                "success": False,
                                "failure_reason": "no_golden_dataset",
                            },
                            source="calibration_mixin",
                        ))
                        return

                    golden_data = []
                    for sample in dataset.samples[:20]:
                        if sample.scores:
                            expert_score = sum(sample.scores.values()) / len(sample.scores)
                            golden_data.append({
                                "request": sample.input_data,
                                "expert_score": expert_score,
                            })

                    if not golden_data:
                        logger.warning(f"自愈失败: 评估器 {evaluator_name} 没有带标注的样本")
                        bus.publish(Event(
                            event_type=EventType.SELF_HEALING_COMPLETED,
                            payload={
                                "evaluator_name": evaluator_name,
                                "success": False,
                                "failure_reason": "no_labeled_samples",
                            },
                            source="calibration_mixin",
                        ))
                        return

                    before_result = calibration_manager.run_calibration(
                        trigger=CalibrationTrigger.DRIFT_DETECTED,
                        evaluator=self,
                        golden_dataset=golden_data,
                    )
                    before_deviation = before_result.deviation if before_result.deviation is not None else 1.0

                    if not before_result.success:
                        logger.warning(
                            f"自愈前置校准失败 | evaluator={evaluator_name} | "
                            f"deviation={before_deviation:.4f}"
                        )

                    result = calibration_manager.run_calibration(
                        trigger=CalibrationTrigger.DRIFT_DETECTED,
                        evaluator=self,
                        golden_dataset=golden_data,
                    )

                    after_deviation = result.deviation if result.deviation is not None else 1.0
                    improvement = (before_deviation - after_deviation) / max(before_deviation, 1e-9) if before_deviation > 0 else 1e-9

                    if result.success:
                        self._self_healing_failure_counts[evaluator_name] = 0
                        if improvement > 0:
                            logger.info(
                                f"自愈成功 | evaluator={evaluator_name} | "
                                f"before={before_deviation:.4f} | after={after_deviation:.4f} | "
                                f"improvement={improvement:.2%}"
                            )
                        else:
                            logger.warning(
                                f"自愈完成但无改善 | evaluator={evaluator_name} | "
                                f"before={before_deviation:.4f} | after={after_deviation:.4f} | "
                                f"improvement={improvement:.2%} | 需要人工干预"
                            )

                        bus.publish(Event(
                            event_type=EventType.SELF_HEALING_COMPLETED,
                            payload={
                                "evaluator_name": evaluator_name,
                                "success": True,
                                "before_deviation": before_deviation,
                                "after_deviation": after_deviation,
                                "improvement": improvement,
                            },
                            source="calibration_mixin",
                        ))
                    else:
                        current_count = self._self_healing_failure_counts.get(evaluator_name, 0)
                        self._self_healing_failure_counts[evaluator_name] = current_count + 1
                        logger.error(
                            f"自愈失败 | evaluator={evaluator_name} | "
                            f"deviation={after_deviation:.4f} | 需要人工干预"
                        )
                        bus.publish(Event(
                            event_type=EventType.SELF_HEALING_COMPLETED,
                            payload={
                                "evaluator_name": evaluator_name,
                                "success": False,
                                "before_deviation": before_deviation,
                                "after_deviation": after_deviation,
                                "failure_reason": "calibration_failed",
                            },
                            source="calibration_mixin",
                        ))
                except Exception as e:
                    logger.error(f"自愈任务失败: {e}")
                    current_count = self._self_healing_failure_counts.get(evaluator_name, 0)
                    self._self_healing_failure_counts[evaluator_name] = current_count + 1
                    try:
                        from src.infra.event_bus import EventBus, Event, EventType
                        bus = EventBus()
                        bus.publish(Event(
                            event_type=EventType.SELF_HEALING_COMPLETED,
                            payload={
                                "evaluator_name": evaluator_name,
                                "success": False,
                                "failure_reason": f"exception: {str(e)}",
                            },
                            source="calibration_mixin",
                        ))
                    except Exception:
                        pass

            thread = threading.Thread(target=self_healing_task, daemon=True)
            thread.start()
        except Exception as e:
            logger.error(f"启动自愈流程失败: {e}")
