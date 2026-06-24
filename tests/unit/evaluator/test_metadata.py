"""
Metadata 模型专项测试
测试目标：验证4个Pydantic元数据模型的核心能力（BaseMetadata/FinanceMetadata/CodeMetadata/TextMetadata）
关键发现：4个元数据模型继承自BaseMetadata，各有扩展字段，被多个评估器（code/finance/text等）依赖
"""

from src.domain.evaluators.metadata import (
    BaseMetadata,
    CodeMetadata,
    FinanceMetadata,
    TextMetadata,
)


class TestBaseMetadata:
    """基础元数据模型测试"""

    def test_default_values(self):
        """默认值应正确设置"""
        metadata = BaseMetadata()
        assert metadata.priority == "normal"
        assert metadata.debug_mode is False

    def test_custom_values(self):
        """自定义值应正确设置"""
        metadata = BaseMetadata(priority="high", debug_mode=True)
        assert metadata.priority == "high"
        assert metadata.debug_mode is True

    def test_priority_validation(self):
        """priority字段应接受字符串"""
        metadata = BaseMetadata(priority="low")
        assert metadata.priority == "low"

    def test_debug_mode_validation(self):
        """debug_mode字段应接受布尔值"""
        metadata = BaseMetadata(debug_mode=False)
        assert metadata.debug_mode is False

    def test_to_dict(self):
        """应能正确转换为字典"""
        metadata = BaseMetadata(priority="high", debug_mode=True)
        result = metadata.model_dump()
        assert result == {"priority": "high", "debug_mode": True}


class TestFinanceMetadata:
    """金融元数据模型测试"""

    def test_default_values(self):
        """默认值应正确设置"""
        metadata = FinanceMetadata()
        assert metadata.priority == "normal"
        assert metadata.debug_mode is False
        assert metadata.rate == 0.0
        assert metadata.target == "general"

    def test_custom_values(self):
        """自定义值应正确设置"""
        metadata = FinanceMetadata(
            priority="high",
            debug_mode=True,
            rate=0.05,
            target="investment",
        )
        assert metadata.priority == "high"
        assert metadata.debug_mode is True
        assert metadata.rate == 0.05
        assert metadata.target == "investment"

    def test_rate_validation(self):
        """rate字段应接受浮点数"""
        metadata = FinanceMetadata(rate=0.1)
        assert metadata.rate == 0.1

    def test_target_validation(self):
        """target字段应接受字符串"""
        metadata = FinanceMetadata(target="loan")
        assert metadata.target == "loan"

    def test_inheritance(self):
        """应继承自BaseMetadata"""
        metadata = FinanceMetadata()
        assert isinstance(metadata, BaseMetadata)

    def test_to_dict(self):
        """应能正确转换为字典"""
        metadata = FinanceMetadata(rate=0.03, target="savings")
        result = metadata.model_dump()
        assert result == {
            "priority": "normal",
            "debug_mode": False,
            "rate": 0.03,
            "target": "savings",
        }


class TestCodeMetadata:
    """代码元数据模型测试"""

    def test_default_values(self):
        """默认值应正确设置"""
        metadata = CodeMetadata()
        assert metadata.priority == "normal"
        assert metadata.debug_mode is False
        assert metadata.language == "python"
        assert metadata.style_guide == "pep8"

    def test_custom_values(self):
        """自定义值应正确设置"""
        metadata = CodeMetadata(
            priority="high",
            debug_mode=True,
            language="javascript",
            style_guide="airbnb",
        )
        assert metadata.priority == "high"
        assert metadata.debug_mode is True
        assert metadata.language == "javascript"
        assert metadata.style_guide == "airbnb"

    def test_language_validation(self):
        """language字段应接受字符串"""
        metadata = CodeMetadata(language="go")
        assert metadata.language == "go"

    def test_style_guide_validation(self):
        """style_guide字段应接受字符串"""
        metadata = CodeMetadata(style_guide="google")
        assert metadata.style_guide == "google"

    def test_inheritance(self):
        """应继承自BaseMetadata"""
        metadata = CodeMetadata()
        assert isinstance(metadata, BaseMetadata)

    def test_to_dict(self):
        """应能正确转换为字典"""
        metadata = CodeMetadata(language="java", style_guide="google")
        result = metadata.model_dump()
        assert result == {
            "priority": "normal",
            "debug_mode": False,
            "language": "java",
            "style_guide": "google",
        }


class TestTextMetadata:
    """文本元数据模型测试"""

    def test_default_values(self):
        """默认值应正确设置"""
        metadata = TextMetadata()
        assert metadata.priority == "normal"
        assert metadata.debug_mode is False
        assert metadata.tone == "neutral"

    def test_custom_values(self):
        """自定义值应正确设置"""
        metadata = TextMetadata(
            priority="high",
            debug_mode=True,
            tone="formal",
        )
        assert metadata.priority == "high"
        assert metadata.debug_mode is True
        assert metadata.tone == "formal"

    def test_tone_validation(self):
        """tone字段应接受字符串"""
        metadata = TextMetadata(tone="friendly")
        assert metadata.tone == "friendly"

    def test_inheritance(self):
        """应继承自BaseMetadata"""
        metadata = TextMetadata()
        assert isinstance(metadata, BaseMetadata)

    def test_to_dict(self):
        """应能正确转换为字典"""
        metadata = TextMetadata(tone="professional")
        result = metadata.model_dump()
        assert result == {
            "priority": "normal",
            "debug_mode": False,
            "tone": "professional",
        }


class TestMetadataIntegration:
    """集成测试"""

    def test_all_models_have_consistent_defaults(self):
        """所有模型应具有一致的默认值"""
        base = BaseMetadata()
        finance = FinanceMetadata()
        code = CodeMetadata()
        text = TextMetadata()

        assert base.priority == finance.priority == code.priority == text.priority
        assert base.debug_mode == finance.debug_mode == code.debug_mode == text.debug_mode

    def test_all_models_can_be_instantiated(self):
        """所有模型应能被实例化"""
        BaseMetadata()
        FinanceMetadata()
        CodeMetadata()
        TextMetadata()

    def test_all_models_support_model_dump(self):
        """所有模型应支持model_dump"""
        assert isinstance(BaseMetadata().model_dump(), dict)
        assert isinstance(FinanceMetadata().model_dump(), dict)
        assert isinstance(CodeMetadata().model_dump(), dict)
        assert isinstance(TextMetadata().model_dump(), dict)

    def test_all_models_inherit_from_base(self):
        """所有模型应继承自BaseMetadata"""
        assert issubclass(FinanceMetadata, BaseMetadata)
        assert issubclass(CodeMetadata, BaseMetadata)
        assert issubclass(TextMetadata, BaseMetadata)
