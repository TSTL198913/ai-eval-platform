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

    def test_custom_values(self):
        """自定义值应正确设置"""
        metadata = BaseMetadata()
        result = metadata.model_dump()
        assert result == {}

    def test_to_dict(self):
        """应能正确转换为字典"""
        metadata = BaseMetadata()
        result = metadata.model_dump()
        assert result == {}


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

    def test_regulations_validation(self):
        """regulations字段应接受列表"""
        metadata = FinanceMetadata(regulations=["test"])
        assert metadata.regulations == ["test"]

    def test_jurisdiction_validation(self):
        """jurisdiction字段应接受字符串"""
        metadata = FinanceMetadata(jurisdiction="EU")
        assert metadata.jurisdiction == "EU"

    def test_to_dict(self):
        """应能正确转换为字典"""
        metadata = FinanceMetadata(regulations=["SOX"], jurisdiction="US")
        result = metadata.model_dump()
        assert result == {
            "regulations": ["SOX"],
            "jurisdiction": "US",
        }


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

    def test_language_validation(self):
        """language字段应接受字符串"""
        metadata = TextMetadata(language="ja")
        assert metadata.language == "ja"

    def test_to_dict(self):
        """应能正确转换为字典"""
        metadata = TextMetadata(language="en", max_length=5000)
        result = metadata.model_dump()
        assert result == {
            "language": "en",
            "max_length": 5000,
        }


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

    def test_code_metadata_inherits_from_base(self):
        """CodeMetadata应继承自BaseMetadata"""
        assert issubclass(CodeMetadata, BaseMetadata)
