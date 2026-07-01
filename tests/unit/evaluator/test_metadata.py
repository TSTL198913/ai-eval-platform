"""
Metadata 模型专项测试
测试目标：验证4个Pydantic元数据模型的核心能力（BaseMetadata/FinanceMetadata/CodeMetadata/TextMetadata）
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
        result = metadata.model_dump()
        assert result == {}

    def test_empty_instance(self):
        """空实例应无任何字段"""
        metadata = BaseMetadata()
        assert len(metadata.model_fields) == 0


class TestFinanceMetadata:
    """金融元数据模型测试"""

    def test_default_values(self):
        """默认值应正确设置"""
        metadata = FinanceMetadata()
        assert metadata.regulations == []
        assert metadata.jurisdiction == "CN"

    def test_custom_values(self):
        """自定义值应正确设置"""
        metadata = FinanceMetadata(
            regulations=["GB/T 19001", "SOX"],
            jurisdiction="US",
        )
        assert metadata.regulations == ["GB/T 19001", "SOX"]
        assert metadata.jurisdiction == "US"

    def test_regulations_accepts_multiple_items(self):
        """regulations字段应接受多个监管项"""
        metadata = FinanceMetadata(regulations=["SOX", "GDPR", "PCI-DSS"])
        assert len(metadata.regulations) == 3
        assert "SOX" in metadata.regulations
        assert "GDPR" in metadata.regulations

    def test_jurisdiction_supports_standard_codes(self):
        """jurisdiction字段应支持标准国家代码"""
        metadata = FinanceMetadata(jurisdiction="US")
        assert metadata.jurisdiction == "US"
        metadata = FinanceMetadata(jurisdiction="EU")
        assert metadata.jurisdiction == "EU"

    def test_to_dict_serializes_correctly(self):
        """应能正确序列化为字典"""
        metadata = FinanceMetadata(regulations=["SOX"], jurisdiction="US")
        result = metadata.model_dump()
        assert result == {
            "regulations": ["SOX"],
            "jurisdiction": "US",
        }

    def test_inheritance(self):
        """应继承自BaseMetadata"""
        metadata = FinanceMetadata()
        assert isinstance(metadata, BaseMetadata)


class TestCodeMetadata:
    """代码元数据模型测试"""

    def test_default_values(self):
        """默认值应正确设置"""
        metadata = CodeMetadata()
        assert metadata.language == "python"
        assert metadata.timeout == 5
        assert metadata.memory_limit_mb == 256
        assert metadata.style_guide == ""

    def test_custom_values(self):
        """自定义值应正确设置"""
        metadata = CodeMetadata(
            language="javascript",
            timeout=10,
            memory_limit_mb=512,
            style_guide="airbnb",
        )
        assert metadata.language == "javascript"
        assert metadata.timeout == 10
        assert metadata.memory_limit_mb == 512
        assert metadata.style_guide == "airbnb"

    def test_timeout_positive_integer(self):
        """timeout字段应为正整数"""
        metadata = CodeMetadata(timeout=30)
        assert metadata.timeout == 30

    def test_memory_limit_reasonable_range(self):
        """memory_limit_mb字段应在合理范围内"""
        metadata = CodeMetadata(memory_limit_mb=1024)
        assert metadata.memory_limit_mb == 1024

    def test_style_guide_recognized_values(self):
        """style_guide字段应接受常见规范"""
        metadata = CodeMetadata(style_guide="google")
        assert metadata.style_guide == "google"
        metadata = CodeMetadata(style_guide="pep8")
        assert metadata.style_guide == "pep8"

    def test_inheritance(self):
        """应继承自BaseMetadata"""
        metadata = CodeMetadata()
        assert isinstance(metadata, BaseMetadata)

    def test_to_dict_serializes_all_fields(self):
        """应能正确序列化所有字段"""
        metadata = CodeMetadata(language="java", style_guide="google")
        result = metadata.model_dump()
        assert result == {
            "language": "java",
            "timeout": 5,
            "memory_limit_mb": 256,
            "style_guide": "google",
        }


class TestTextMetadata:
    """文本元数据模型测试"""

    def test_default_values(self):
        """默认值应正确设置"""
        metadata = TextMetadata()
        assert metadata.language == "zh"
        assert metadata.max_length == 10000

    def test_custom_values(self):
        """自定义值应正确设置"""
        metadata = TextMetadata(
            language="en",
            max_length=5000,
        )
        assert metadata.language == "en"
        assert metadata.max_length == 5000

    def test_language_supports_multiple_codes(self):
        """language字段应支持多语言代码"""
        metadata = TextMetadata(language="ja")
        assert metadata.language == "ja"
        metadata = TextMetadata(language="fr")
        assert metadata.language == "fr"

    def test_max_length_positive_integer(self):
        """max_length字段应为正整数"""
        metadata = TextMetadata(max_length=20000)
        assert metadata.max_length == 20000

    def test_to_dict_serializes_correctly(self):
        """应能正确序列化为字典"""
        metadata = TextMetadata(language="en", max_length=5000)
        result = metadata.model_dump()
        assert result == {
            "language": "en",
            "max_length": 5000,
        }

    def test_inheritance(self):
        """应继承自BaseMetadata"""
        metadata = TextMetadata()
        assert isinstance(metadata, BaseMetadata)


class TestMetadataIntegration:
    """集成测试"""

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

    def test_all_metadata_models_inherit_from_base(self):
        """所有元数据模型应继承自BaseMetadata"""
        assert issubclass(CodeMetadata, BaseMetadata)
        assert issubclass(FinanceMetadata, BaseMetadata)
        assert issubclass(TextMetadata, BaseMetadata)
