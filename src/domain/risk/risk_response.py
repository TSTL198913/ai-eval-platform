from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskResponseStrategy:
    """风险响应策略"""

    @classmethod
    def respond(cls, risk_type: str, risk_level: RiskLevel, data: dict) -> dict:
        strategies = {
            "feature_creep": cls._handle_feature_creep,
            "tech_debt": cls._handle_tech_debt,
            "coupling": cls._handle_coupling,
            "test_coverage": cls._handle_test_coverage,
            "drift": cls._handle_drift,
        }

        handler = strategies.get(risk_type, cls._handle_default)
        return handler(risk_level, data)

    @classmethod
    def _handle_feature_creep(cls, level: RiskLevel, data: dict) -> dict:
        if level == RiskLevel.HIGH:
            return {
                "action": "block",
                "message": "功能蔓延风险过高，请审查需求范围",
                "suggestion": "拆分功能，延期非核心需求，重新评估优先级",
            }
        elif level == RiskLevel.MEDIUM:
            return {
                "action": "warn",
                "message": "检测到中等功能蔓延风险",
                "suggestion": "确认新增功能与核心目标的一致性",
            }
        return {"action": "pass", "message": "功能范围控制良好"}

    @classmethod
    def _handle_tech_debt(cls, level: RiskLevel, data: dict) -> dict:
        if level == RiskLevel.HIGH:
            return {
                "action": "block",
                "message": "技术债务累积过多",
                "suggestion": "优先清理技术债务，制定定期清理计划",
            }
        elif level == RiskLevel.MEDIUM:
            return {
                "action": "warn",
                "message": "技术债务逐步累积",
                "suggestion": "安排时间清理高优先级债务",
            }
        return {"action": "pass", "message": "技术债务控制良好"}

    @classmethod
    def _handle_coupling(cls, level: RiskLevel, data: dict) -> dict:
        if level == RiskLevel.HIGH:
            return {
                "action": "block",
                "message": "模块耦合度过高",
                "suggestion": "引入中间层解耦，减少跨层调用",
            }
        elif level == RiskLevel.MEDIUM:
            return {
                "action": "warn",
                "message": "模块耦合度偏高",
                "suggestion": "审查依赖关系，考虑重构",
            }
        return {"action": "pass", "message": "模块耦合度控制良好"}

    @classmethod
    def _handle_test_coverage(cls, level: RiskLevel, data: dict) -> dict:
        if level == RiskLevel.HIGH:
            return {
                "action": "block",
                "message": "测试覆盖不足",
                "suggestion": "补充测试用例，达到70%覆盖率",
            }
        elif level == RiskLevel.MEDIUM:
            return {
                "action": "warn",
                "message": "测试覆盖率偏低",
                "suggestion": "增加关键路径的测试用例",
            }
        return {"action": "pass", "message": "测试覆盖率良好"}

    @classmethod
    def _handle_drift(cls, level: RiskLevel, data: dict) -> dict:
        if level == RiskLevel.HIGH:
            return {
                "action": "block",
                "message": "检测到显著行为漂移",
                "suggestion": "审查最近代码变更，定位漂移原因",
            }
        elif level == RiskLevel.MEDIUM:
            return {
                "action": "warn",
                "message": "检测到轻微行为漂移",
                "suggestion": "持续监控，确认是否为正常波动",
            }
        return {"action": "pass", "message": "系统行为稳定"}

    @classmethod
    def _handle_default(cls, level: RiskLevel, data: dict) -> dict:
        if level == RiskLevel.HIGH:
            return {"action": "block", "message": "检测到高风险"}
        elif level == RiskLevel.MEDIUM:
            return {"action": "warn", "message": "检测到中等风险"}
        return {"action": "pass", "message": "风险在可控范围内"}

    @classmethod
    def evaluate_all(cls, risk_results: dict) -> dict:
        responses = {}
        overall_action = "pass"
        high_risk_count = 0
        medium_risk_count = 0

        for risk_type, details in risk_results.get("details", {}).items():
            risk_level = details.get("risk_level", "low")
            response = cls.respond(risk_type, RiskLevel(risk_level), details)
            responses[risk_type] = response

            if response["action"] == "block":
                overall_action = "block"
                high_risk_count += 1
            elif response["action"] == "warn":
                medium_risk_count += 1
                if overall_action != "block":
                    overall_action = "warn"

        return {
            "overall_action": overall_action,
            "high_risk_count": high_risk_count,
            "medium_risk_count": medium_risk_count,
            "responses": responses,
        }
