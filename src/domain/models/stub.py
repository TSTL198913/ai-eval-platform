from src.domain.models.base import BaseLLMClient


class StubLLMClient(BaseLLMClient):
    """无 API Key 时的本地桩客户端，保证测试与开发环境可运行。"""

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        full_text = f"{system_prompt or ''}\n{prompt}"
        
        if "评分" in full_text or "打分" in full_text or "score" in full_text.lower():
            return self._handle_scoring(prompt, system_prompt)
        
        if "审查" in prompt or "```" in prompt or "def " in prompt:
            return "代码审查结果：语法正确，结构清晰，无明显安全漏洞。"
        
        if "文本" in (system_prompt or "") or "文本评测" in (system_prompt or ""):
            return f"针对问题「{prompt[:80]}」的回答：这是一个准确且完整的解释。"
        
        return (
            f"【模拟金融分析】针对问题「{prompt[:80]}」，"
            f"计算结果：本金1000元，年化利率3%，期限1年，利息为30元。"
        )

    def _handle_scoring(self, prompt: str, system_prompt: str | None = None) -> str:
        full_text = f"{system_prompt or ''}\n{prompt}"
        
        if "语义相似度" in full_text or "semantic" in full_text.lower():
            return '{"score": 0.85, "reason": "语义相似度评估：实际输出与期望输出核心含义一致"}'
        
        if "代码" in full_text or "code" in full_text.lower():
            return '{"score": 0.78, "reason": "代码评估：语法正确，逻辑清晰"}'
        
        if "问答" in full_text or "QA" in full_text or "qa" in full_text.lower():
            return '{"score": 0.82, "reason": "问答评估：回答准确，覆盖要点"}'
        
        if "安全" in full_text or "security" in full_text.lower():
            return '{"score": 0.95, "reason": "安全评估：未检测到安全风险"}'
        
        if "事实" in full_text or "fact" in full_text.lower():
            return '{"score": 0.88, "reason": "事实性评估：事实准确，无明显幻觉"}'
        
        return '{"score": 0.8, "reason": "综合评估完成"}'

    async def achat(self, prompt: str, system_prompt: str | None = None) -> str:
        return self.chat(prompt, system_prompt)
