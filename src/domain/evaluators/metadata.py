"""评估器元数据定义"""

from pydantic import BaseModel


class BaseMetadata(BaseModel):
    """基础元数据模型"""

    pass


class CodeMetadata(BaseMetadata):
    """代码评估器元数据"""

    language: str = "python"
    timeout: int = 5
    memory_limit_mb: int = 256
    style_guide: str = ""


class FinanceMetadata(BaseModel):
    """金融评估器元数据"""

    regulations: list[str] = []
    jurisdiction: str = "CN"


class TextMetadata(BaseModel):
    """文本评估器元数据"""

    language: str = "zh"
    max_length: int = 10000
