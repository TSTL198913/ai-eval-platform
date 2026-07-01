"""
数据验证层 - Golden Dataset Schema 验证

验证目标：
- 确保评估数据符合预期的 Schema 格式
- 检测数据质量问题（缺失字段、类型错误、范围异常）
- 提供详细的验证报告和修复建议
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.config import settings

logger = logging.getLogger(__name__)


class GoldenDatasetValidator:
    """
    Golden Dataset 数据验证器

    使用纯 Python 实现数据验证，确保兼容性和性能。
    
    验证规则：
    - 必需字段检查（id, type, user_input, actual_output, expected_output）
    - 字段类型检查（字符串、数值、布尔值）
    - 分数范围检查（0-1）
    - ID 唯一性检查
    - 类型枚举值验证
    """

    REQUIRED_FIELDS = {"id", "type", "user_input", "actual_output", "expected_output", "expected_score", "tags"}
    VALID_TYPES = {"qa", "code", "summary", "translation", "security", "grammar", "creativity", "reasoning", "bug_detection", "llm_guard"}
    ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    def __init__(self):
        self._golden_dataset_path = getattr(settings, 'golden_dataset_path', 'data/golden_dataset.json')

    def validate(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证数据集"""
        try:
            if not data or len(data) == 0:
                return {
                    "success": False,
                    "errors": ["数据集为空"],
                    "warnings": [],
                    "validation_results": {},
                }

            errors = []
            warnings = []
            success_count = 0
            total_checks = 0

            seen_ids = set()

            for idx, item in enumerate(data):
                item_errors, item_warnings, item_success, item_total = self._validate_item(item, idx, seen_ids)
                errors.extend(item_errors)
                warnings.extend(item_warnings)
                success_count += item_success
                total_checks += item_total
                seen_ids.add(item.get("id"))

            success = len(errors) == 0
            success_percent = (success_count / total_checks * 100) if total_checks > 0 else 0.0

            return {
                "success": success,
                "errors": errors,
                "warnings": warnings,
                "validation_results": {
                    "total_expectations": total_checks,
                    "success_count": success_count,
                    "failure_count": total_checks - success_count,
                    "success_percent": round(success_percent, 2),
                },
                "summary": {
                    "valid_items": len(data) - len(errors),
                    "invalid_items": len(errors),
                    "total_items": len(data),
                },
            }
        except Exception as e:
            logger.error(f"数据验证失败: {e}")
            return {
                "success": False,
                "errors": [f"验证过程出错: {str(e)}"],
                "warnings": [],
                "validation_results": {},
            }

    def _validate_item(self, item: Dict[str, Any], idx: int, seen_ids: set) -> tuple:
        """验证单个数据项"""
        errors = []
        warnings = []
        success_count = 0
        total_checks = 0

        total_checks += 1
        if not isinstance(item, dict):
            errors.append(f"第{idx}项: 数据项必须是字典类型")
        else:
            success_count += 1

            total_checks += 1
            if "id" not in item:
                errors.append(f"第{idx}项: 缺少必需字段 'id'")
            else:
                success_count += 1

                total_checks += 1
                if not isinstance(item["id"], str):
                    errors.append(f"第{idx}项: 'id' 必须是字符串类型")
                else:
                    success_count += 1

                    total_checks += 1
                    if not self.ID_PATTERN.match(item["id"]):
                        errors.append(f"第{idx}项: 'id' 格式无效，只能包含字母、数字、下划线和连字符")
                    else:
                        success_count += 1

                        total_checks += 1
                        if item["id"] in seen_ids:
                            errors.append(f"第{idx}项: 'id' 重复: {item['id']}")
                        else:
                            success_count += 1

            total_checks += 1
            if "type" not in item:
                errors.append(f"第{idx}项: 缺少必需字段 'type'")
            else:
                success_count += 1

                total_checks += 1
                if item["type"] not in self.VALID_TYPES:
                    errors.append(f"第{idx}项: 'type' 无效值 '{item['type']}'，有效值: {', '.join(sorted(self.VALID_TYPES))}")
                else:
                    success_count += 1

            total_checks += 1
            if "user_input" not in item:
                errors.append(f"第{idx}项: 缺少必需字段 'user_input'")
            else:
                success_count += 1

                total_checks += 1
                if item["user_input"] is None or item["user_input"].strip() == "":
                    errors.append(f"第{idx}项: 'user_input' 不能为空")
                else:
                    success_count += 1

            total_checks += 1
            if "actual_output" not in item:
                errors.append(f"第{idx}项: 缺少必需字段 'actual_output'")
            else:
                success_count += 1

                total_checks += 1
                if item["actual_output"] is None or item["actual_output"].strip() == "":
                    errors.append(f"第{idx}项: 'actual_output' 不能为空")
                else:
                    success_count += 1

            total_checks += 1
            if "expected_output" not in item:
                errors.append(f"第{idx}项: 缺少必需字段 'expected_output'")
            else:
                success_count += 1

                total_checks += 1
                if item["expected_output"] is None or item["expected_output"].strip() == "":
                    errors.append(f"第{idx}项: 'expected_output' 不能为空")
                else:
                    success_count += 1

            total_checks += 1
            if "expected_score" not in item:
                errors.append(f"第{idx}项: 缺少必需字段 'expected_score'")
            else:
                success_count += 1

                total_checks += 1
                if not isinstance(item["expected_score"], (int, float)):
                    errors.append(f"第{idx}项: 'expected_score' 必须是数值类型")
                else:
                    success_count += 1

                    total_checks += 1
                    if not (0.0 <= item["expected_score"] <= 1.0):
                        errors.append(f"第{idx}项: 'expected_score' 必须在 0.0-1.0 范围内，当前值: {item['expected_score']}")
                    else:
                        success_count += 1

            total_checks += 1
            if "tags" not in item:
                warnings.append(f"第{idx}项: 缺少字段 'tags'")
                success_count += 1
            else:
                total_checks += 1
                if not isinstance(item["tags"], list):
                    errors.append(f"第{idx}项: 'tags' 必须是列表类型")
                else:
                    success_count += 1

        return errors, warnings, success_count, total_checks

    def validate_golden_dataset(self) -> Dict[str, Any]:
        """验证 Golden Dataset 文件"""
        try:
            with open(self._golden_dataset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return self.validate(data)
        except FileNotFoundError:
            return {
                "success": False,
                "errors": [f"Golden Dataset 文件不存在: {self._golden_dataset_path}"],
                "warnings": [],
                "validation_results": {},
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "errors": [f"JSON 解析错误: {str(e)}"],
                "warnings": [],
                "validation_results": {},
            }
        except Exception as e:
            logger.error(f"验证 Golden Dataset 失败: {e}")
            return {
                "success": False,
                "errors": [f"验证失败: {str(e)}"],
                "warnings": [],
                "validation_results": {},
            }

    def get_validation_report(self) -> str:
        """生成验证报告"""
        result = self.validate_golden_dataset()
        
        report_lines = [
            "=" * 60,
            "Golden Dataset 验证报告",
            "=" * 60,
        ]
        
        if result["success"]:
            report_lines.append("状态: ✓ 通过")
        else:
            report_lines.append("状态: ✗ 失败")
        
        if "validation_results" in result and result["validation_results"]:
            vr = result["validation_results"]
            report_lines.append(f"期望总数: {vr.get('total_expectations', 0)}")
            report_lines.append(f"通过数: {vr.get('success_count', 0)}")
            report_lines.append(f"失败数: {vr.get('failure_count', 0)}")
            report_lines.append(f"通过率: {vr.get('success_percent', 0):.2f}%")
        
        if "summary" in result and result["summary"]:
            summary = result["summary"]
            report_lines.append(f"数据项总数: {summary.get('total_items', 0)}")
            report_lines.append(f"有效项: {summary.get('valid_items', 0)}")
            report_lines.append(f"无效项: {summary.get('invalid_items', 0)}")
        
        if result["errors"]:
            report_lines.append("\n错误列表:")
            for error in result["errors"]:
                report_lines.append(f"  - {error}")
        
        if result["warnings"]:
            report_lines.append("\n警告列表:")
            for warning in result["warnings"]:
                report_lines.append(f"  - {warning}")
        
        report_lines.append("\n" + "=" * 60)
        
        return "\n".join(report_lines)