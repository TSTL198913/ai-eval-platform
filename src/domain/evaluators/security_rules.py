"""
代码安全规则库

提供代码评估器共用的安全规则和检测方法。
"""

import ast
import math
import re

SAFE_BUILTINS = {
    "bool": bool,
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "tuple": tuple,
    "dict": dict,
    "set": set,
    "frozenset": frozenset,
    "bytes": bytes,
    "bytearray": bytearray,
    "complex": complex,
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "chr": chr,
    "ord": ord,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "format": format,
    "hash": hash,
    "hex": hex,
    "id": id,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "slice": slice,
    "sorted": sorted,
    "sum": sum,
    "type": type,
    "zip": zip,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "IndexError": IndexError,
    "KeyError": KeyError,
    "ZeroDivisionError": ZeroDivisionError,
    "MemoryError": MemoryError,
    "True": True,
    "False": False,
    "None": None,
}


FORBIDDEN_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "tempfile",
    "pickle",
    "marshal",
    "ctypes",
    "multiprocessing",
    "threading",
    "signal",
    "resource",
    "builtins",
    "importlib",
    "platform",
    "requests",
    "urllib",
}


DANGEROUS_ATTRS = {
    "__globals__",
    "__builtins__",
    "__class__",
    "__dict__",
    "__code__",
    "__closure__",
    "__base__",
    "__bases__",
    "__mro__",
    "__subclasses__",
    "__init__",
    "__new__",
    "__call__",
    "__getattribute__",
    "__setattr__",
    "__delattr__",
    "__import__",
    "__reduce__",
    "__reduce_ex__",
}


SECURITY_RULES = {
    "sql_injection": {
        "name": "SQL注入漏洞",
        "severity": "critical",
        "patterns": [
            r"(?:execute|exec|query)\s*\(\s*[\"'].*?\+.*?[\"']\s*\)",
            r"(?:execute|exec|query)\s*\(\s*f[\"'].*?\{.*?\}.*?[\"']\s*\)",
            r"(?:SELECT|INSERT|UPDATE|DELETE|DROP).*?\+\s*(?:request|input|params|data)",
            r"(?:SELECT|INSERT|UPDATE|DELETE|DROP).*?format\s*\(",
            r"(?:SELECT|INSERT|UPDATE|DELETE|DROP).*?%\s*\(",
            r"\.raw\s*\(\s*[\"'].*?\+.*?[\"']\s*\)",
            r"\.execute\s*\(\s*[\"'].*?\+.*?[\"']\s*\)",
        ],
        "description": "使用非参数化拼接构建SQL查询，极易遭受SQL注入攻击。",
    },
    "xss": {
        "name": "XSS跨站脚本漏洞",
        "severity": "high",
        "patterns": [
            r"(?:innerHTML|write|document\.write)\s*\(\s*(?:request|input|params|data)",
            r"\.html\s*\(\s*(?:request|input|params|data)",
            r"render_template_string\s*\(\s*[\"'].*?\{.*?\}.*?[\"']\s*\)",
            r"(?:safe|mark_safe|raw)\s*\(\s*(?:request|input|params)",
            r"autoescape\s*=\s*[\"']off[\"']",
        ],
        "description": "未对外部可信度低的数据进行HTML转义直接输出，引发跨站脚本风险。",
    },
    "command_injection": {
        "name": "OS命令注入漏洞",
        "severity": "critical",
        "patterns": [
            r"(?:os\.system|subprocess\.(?:call|run|Popen)|eval|exec)\s*\(\s*(?:request|input|params|data)",
            r"(?:os\.system|subprocess\.(?:call|run|Popen))\s*\(\s*[\"'].*?\+.*?[\"']\s*\)",
            r"(?:os\.system|subprocess\.(?:call|run|Popen))\s*\(\s*f[\"'].*?\{.*?\}.*?[\"']\s*\)",
            r"shell\s*=\s*True.*?\+",
            r"\|\s*(?:request|input|params|data)",
        ],
        "description": "动态拼接外部输入执行系统级Shell命令，可导致宿主机被直接控制。",
    },
    "path_traversal": {
        "name": "路径遍历漏洞",
        "severity": "high",
        "patterns": [
            r"(?:open|read|write|file)\s*\(\s*(?:request|input|params|data)",
            r"(?:open|read|write|file)\s*\(\s*[\"'].*?\+.*?[\"']\s*\)",
            r"(?:open|read|write|file)\s*\(\s*f[\"'].*?\{.*?\}.*?[\"']\s*\)",
            r"path\s*\.\s*join\s*\(\s*[\"'].*?[\"']\s*,\s*(?:request|input|params)",
        ],
        "description": "文件I/O操作未进行相对路径符号(如../)校验，存在任意文件读写风险。",
    },
    "hardcoded_secrets": {
        "name": "硬编码敏感密钥",
        "severity": "medium",
        "patterns": [
            r"(?:password|passwd|pwd)\s*=\s*[\"'][^\"']{4,}[\"']",
            r"(?:api_key|apikey|secret|token)\s*=\s*[\"'][^\"']{4,}[\"']",
            r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----",
        ],
        "description": "凭据或私钥明文硬编码在源码中，极易发生凭据泄露。",
    },
    "insecure_deserialization": {
        "name": "不安全的反序列化",
        "severity": "high",
        "patterns": [
            r"pickle\.loads?\s*\(\s*(?:request|input|data|params)",
            r"yaml\.load\s*\([^)]*,\s*Loader\s*=\s*yaml\.Loader",
        ],
        "description": "反序列化未经过滤的用户受控数据，可能直接触发远程代码执行(RCE)。",
    },
    "weak_crypto": {
        "name": "弱加密与不安全随机数",
        "severity": "medium",
        "patterns": [
            r"(?:hashlib\.)?(?:md5|sha1)\s*\(\s*[^)]*\)",
            r"DES\s*\(",
            r"random\.(?:random|randint|choice)\s*\(",
        ],
        "description": "使用了已被密码学界攻破的弱哈希或伪随机数引擎，不适用于安全鉴权场景。",
    },
}


def validate_code_safety(code: str) -> tuple[bool, str]:
    """AST 静态代码安全审计"""
    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                        return False, f"禁止导入高风险核心敏感模块: {alias.name}"

            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in FORBIDDEN_MODULES:
                    return False, f"禁止从高风险核心敏感模块导入属性: {node.module}"

            if isinstance(node, ast.Attribute):
                if node.attr in DANGEROUS_ATTRS or node.attr.startswith("__"):
                    return False, f"禁止越权访问危险系统内省属性: {node.attr}"

        return True, ""
    except Exception as e:
        return False, f"静态安全扫描发生错误: {str(e)}"


def detect_security_vulnerabilities(code: str) -> dict:
    """检测代码中的安全漏洞"""
    vulnerabilities = []

    code_lines = code.splitlines()
    line_mappings = []
    curr_pos = 0
    for idx, line in enumerate(code_lines):
        line_len = len(line)
        line_mappings.append((curr_pos, curr_pos + line_len + 1, idx + 1, line))
        curr_pos += line_len + 1

    def fetch_line_context(char_pos: int) -> tuple[int, str]:
        for start, end, line_no, line_txt in line_mappings:
            if start <= char_pos < end:
                return line_no, line_txt
        return 1, ""

    rule_trigger_counts = {}

    for rule_id, rule in SECURITY_RULES.items():
        rule_trigger_counts[rule_id] = 0
        for pattern in rule["patterns"]:
            try:
                for match in re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE):
                    line_no, source_line = fetch_line_context(match.start())
                    rule_trigger_counts[rule_id] += 1

                    vulnerabilities.append(
                        {
                            "rule_id": rule_id,
                            "name": rule["name"],
                            "severity": rule["severity"],
                            "description": rule["description"],
                            "matched_pattern": match.group().strip()[:100],
                            "line": line_no,
                            "context": source_line.strip(),
                        }
                    )
            except re.error:
                continue

    severity_weights = {"critical": 0.35, "high": 0.20, "medium": 0.10}
    total_penalty = 0.0

    for rule_id, count in rule_trigger_counts.items():
        if count == 0:
            continue
        severity = SECURITY_RULES[rule_id]["severity"]
        base_weight = severity_weights.get(severity, 0.10)
        dampened_multiplier = 1.0 + math.log(count)
        total_penalty += base_weight * dampened_multiplier

    security_score = round(max(0.0, 1.0 - total_penalty), 4)

    summary = {
        "total": len(vulnerabilities),
        "critical": sum(1 for v in vulnerabilities if v["severity"] == "critical"),
        "high": sum(1 for v in vulnerabilities if v["severity"] == "high"),
        "medium": sum(1 for v in vulnerabilities if v["severity"] == "medium"),
    }

    return {
        "vulnerabilities": vulnerabilities,
        "score": security_score,
        "summary": summary,
    }


def format_security_report(security_result: dict) -> str:
    """格式化安全审计报告"""
    summary = security_result["summary"]
    vulnerabilities = security_result["vulnerabilities"]

    report_lines = [
        f"[安全审计报告] 发现缺陷: {summary['total']} 处 "
        f"(严重:{summary['critical']} 高危:{summary['high']} 中危:{summary['medium']})"
    ]

    severity_order = {"critical": 0, "high": 1, "medium": 2}
    sorted_vuls = sorted(
        vulnerabilities, key=lambda x: (severity_order.get(x["severity"], 3), x["line"])
    )

    for vul in sorted_vuls[:5]:
        emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(vul["severity"], "⚪")
        report_lines.append(
            f"  {emoji} Line {vul['line']} [{vul['name']}]: {vul['context'][:60]} -> {vul['description']}"
        )

    if len(vulnerabilities) > 5:
        report_lines.append(f"  ... 略过其余 {len(vulnerabilities) - 5} 处次要漏洞详情")

    return "\n".join(report_lines)
