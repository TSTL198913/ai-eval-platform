import pytest
from src.domain.models.base import BaseLLMClient, ModelConfig


# 模拟一个未实现所有方法的“非法”实现类，用于测试基类约束
class IncompleteClient(BaseLLMClient):
    def chat(self, prompt: str, system_prompt=None) -> str:
        return "incomplete"

    # 故意遗漏 achat 方法


def test_abstract_class_enforcement():
    """验证基类是否强制要求子类实现抽象方法"""
    config = ModelConfig(api_key="sk-123", model_name="test-model")

    with pytest.raises(TypeError):
        # 实例化一个未实现所有抽象方法的类应该报错
        IncompleteClient(config)


def test_model_config_integrity():
    """验证配置项是否正确注入"""
    config = ModelConfig(api_key="sk-test-key", model_name="gpt-4", temperature=0.5)
    assert config.model_name == "gpt-4"
    assert config.temperature == 0.5
    # 验证 SecretStr 安全特性
    assert "sk-test-key" not in str(config.api_key)
