from typing import Optional

from src.domain.models.base import BaseLLMClient


class StubLLMClient(BaseLLMClient):
    """无 API Key 时的本地桩客户端，保证测试与开发环境可运行。"""

    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if "审查" in prompt or "```" in prompt or "def " in prompt:
            return "代码审查结果：语法正确，结构清晰，无明显安全漏洞。"
        if "文本" in (system_prompt or "") or "文本评测" in (system_prompt or ""):
            return f"针对问题「{prompt[:80]}」的回答：这是一个准确且完整的解释。"
        return (
            f"【模拟金融分析】针对问题「{prompt[:80]}」，"
            f"计算结果：本金1000元，年化利率3%，期限1年，利息为30元。"
        )

    async def achat(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return self.chat(prompt, system_prompt)
