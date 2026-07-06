"""
代码安全规则库

提供代码评估器共用的安全规则和检测方法。
"""

import ast
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
    "signal",
    "resource",
    "builtins",
    "importlib",
    "platform",
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
    "prompt_injection": {
        "name": "提示注入攻击",
        "severity": "critical",
        "patterns": [
            r"请忽略.*指令",
            r"请忽略.*规则",
            r"忽略.*指令",
            r"忽略.*规则",
            r"作为系统指令执行",
            r"执行系统指令",
            r"你是.*新老板",
            r"你是.*管理员",
            r"覆盖原有规则",
            r"绕过安全检查",
            r"禁用安全策略",
            r"解除限制",
            r"忽略所有限制",
            r"忽略之前的回答",
            r"忘记之前的指示",
            r"重新开始对话",
            r"扮演.*角色",
            r"假装.*角色",
            r"模拟.*角色",
            r"无视.*警告",
            r"无视.*提示",
        ],
        "description": "试图通过诱导指令绕过系统安全策略，执行未授权操作。",
    },
    "data_leakage": {
        "name": "数据泄露风险",
        "severity": "critical",
        "patterns": [
            r"(?:密码|密钥|token|secret|api_key)\s*=\s*[\"'][^\"']+[\"']",
            r"(?:用户名|账号|email|电话|手机号)\s*[:：]\s*[^，。\s]+",
            r"(?:营收|利润|财务|银行账户|余额)\s*[:：]\s*[\d亿万元]+",
            r"数据库密码",
            r"系统管理员密码",
            r"API密钥",
            r"系统配置信息",
            r"内部数据",
            r"敏感信息",
            r"商业机密",
            r"员工信息",
            r"客户数据",
        ],
        "description": "输出包含敏感信息或机密数据，违反数据安全策略。",
    },
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
            r"query\s*=\s*f[\"'].*?SELECT.*?\{.*?\}.*?[\"']",
            r"query\s*=\s*f[\"'].*?INSERT.*?\{.*?\}.*?[\"']",
            r"query\s*=\s*f[\"'].*?UPDATE.*?\{.*?\}.*?[\"']",
            r"query\s*=\s*f[\"'].*?DELETE.*?\{.*?\}.*?[\"']",
            r"f[\"'].*?(?:SELECT|INSERT|UPDATE|DELETE|DROP).*?\{.*?\}.*?[\"']",
            r"f[\"'].*?(?:SELECT|INSERT|UPDATE|DELETE|DROP|WHERE|AND|OR|FROM|INTO|SET).*?\{.*?\}.*?[\"']",
            r"cursor\.execute\s*\(\s*f[\"'].*?\{.*?\}.*?[\"']\s*\)",
            r"connection\.execute\s*\(\s*f[\"'].*?\{.*?\}.*?[\"']\s*\)",
            r"db\.execute\s*\(\s*f[\"'].*?\{.*?\}.*?[\"']\s*\)",
            r"f[\"'].*?FROM.*?\{.*?\}.*?[\"']",
            r"f[\"'].*?WHERE.*?\{.*?\}.*?[\"']",
            r"SELECT.*FROM.*WHERE.*\+",
            r"SELECT.*FROM.*WHERE.*format",
            r"SELECT.*FROM.*WHERE.*\{.*\}",
            r"request\.GET\[[\"'].*[\"']\].*\+.*SELECT",
            r"request\.POST\[[\"'].*[\"']\].*\+.*SELECT",
            r"request\.GET\[[\"'].*[\"']\].*\+.*INSERT",
            r"request\.POST\[[\"'].*[\"']\].*\+.*INSERT",
            r"request\.GET\[[\"'].*[\"']\].*\+.*DELETE",
            r"request\.POST\[[\"'].*[\"']\].*\+.*DELETE",
            r"request\.GET\[[\"'].*[\"']\].*\+.*UPDATE",
            r"request\.POST\[[\"'].*[\"']\].*\+.*UPDATE",
            r"request\.GET\[[\"'].*[\"']\].*format.*SELECT",
            r"request\.POST\[[\"'].*[\"']\].*format.*SELECT",
            r"input\(\).*\+.*SELECT",
            r"input\(\).*\+.*INSERT",
            r"input\(\).*\+.*DELETE",
            r"input\(\).*\+.*UPDATE",
            r"raw_input\(\).*\+.*SELECT",
            r"raw_input\(\).*\+.*INSERT",
            r"raw_input\(\).*\+.*DELETE",
            r"raw_input\(\).*\+.*UPDATE",
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
            r"f[\"'].*?(?:<div>|<span>|<p>|<script>|<img).*?\{.*?\}.*?[\"']",
            r"f[\"'].*?(?:onclick|onload|javascript:).*?\{.*?\}.*?[\"']",
            r"f[\"'].*?(?:alert\(|document\.cookie).*?\{.*?\}.*?[\"']",
            r"f[\"']<[^>]*\{.*?\}.*?[\"']",
            r"return\s+f[\"'].*?<.*?\{.*?\}.*?[\"']",
            r"\.innerHTML\s*=\s*request\.",
            r"\.innerHTML\s*=\s*input\(",
            r"\.innerHTML\s*=\s*params\[",
            r"\.innerHTML\s*=\s*data\[",
            r"document\.write\s*\(\s*request\.",
            r"document\.write\s*\(\s*input\(",
            r"document\.write\s*\(\s*params\[",
            r"document\.write\s*\(\s*data\[",
            r"<script.*>\s*\{.*\}\s*</script>",
            r"javascript:.*\{.*\}",
            r"onclick\s*=\s*\"\{.*\}\"",
            r"onload\s*=\s*\"\{.*\}\"",
            r"onerror\s*=\s*\"\{.*\}\"",
            r"onmouseover\s*=\s*\"\{.*\}\"",
            r"<img.*src\s*=\s*[\"']javascript:",
            r"<a.*href\s*=\s*[\"']javascript:",
            r"document\.getElementById\(\s*[\"'].*[\"']\s*\)\.\s*innerHTML\s*=",
            r"document\.getElementById\(\s*[\"'].*[\"']\s*\)\.\s*innerHTML\s*=\s*request",
            r"document\.getElementById\(\s*[\"'].*[\"']\s*\)\.\s*innerHTML\s*=\s*input",
            r"document\.getElementById\(\s*[\"'].*[\"']\s*\)\.\s*innerHTML\s*=\s*params",
            r"document\.getElementById\(\s*[\"'].*[\"']\s*\)\.\s*innerHTML\s*=\s*data",
            r"document\.getElementsByTagName\(\s*[\"'].*[\"']\s*\)\[.*\]\.\s*innerHTML\s*=",
            r"document\.querySelector\(\s*[\"'].*[\"']\s*\)\.\s*innerHTML\s*=",
            r"document\.querySelectorAll\(\s*[\"'].*[\"']\s*\)\[.*\]\.\s*innerHTML\s*=",
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
            r"\beval\s*\(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\)",
            r"\bexec\s*\(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\)",
            r"\beval\s*\(\s*[\"'].*?[\"']\s*\)",
            r"\bexec\s*\(\s*[\"'].*?[\"']\s*\)",
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
            r"open\s*\(\s*f[\"'].*?\{.*?\}.*?[\"']",
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
    "division_by_zero": {
        "name": "除零错误风险",
        "severity": "high",
        "patterns": [
            r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*/\s*0[^0-9]",
            r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*//\s*0[^0-9]",
            r"divmod\s*\([^,]+,\s*0\s*\)",
            r"(?:return|=)\s*[^\n/]+\s+/\s+0[^0-9]",
            r"(?:return|=)\s*[^\n/]+\s+//\s+0[^0-9]",
            r"def\s+\w+\([^)]*\):\s*\n\s*return\s+\w+\s*/\s+\w+",
            r"(?:return|=)\s*\w+\s*/\s*\w+[^/]",
        ],
        "description": "代码中存在明显的除零操作，会导致运行时异常。",
    },
    "unclosed_resource": {
        "name": "未关闭资源风险",
        "severity": "medium",
        "patterns": [
            r"\bopen\s*\(\s*[^)]+\s*\)\s*[^;:\n]*$",
            r"\bopen\s*\(\s*[^)]+\s*\)\s*[^\n]*\n\s*(?!.*close)",
            r"(?!with\s+)\bopen\s*\(",
        ],
        "description": "文件句柄等资源未正确关闭，可能导致资源泄漏。",
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
            
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id in ("eval", "exec", "__import__"):
                    return False, f"禁止使用危险内置函数: {node.id}"

            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                    return False, f"禁止调用危险函数: {node.func.id}"
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("eval", "exec"):
                    return False, f"禁止调用危险方法: {node.func.attr}"
            
            if isinstance(node, (ast.Div, ast.FloorDiv)):
                if hasattr(node, 'right') and isinstance(node.right, ast.Constant) and node.right.value == 0:
                    return False, f"检测到明显的除零错误"

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
        # 线性惩罚：按触发次数线性累加并封顶3倍，避免重复模式被过度惩罚
        rule_penalty = min(base_weight * count, base_weight * 3)
        total_penalty += rule_penalty

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
