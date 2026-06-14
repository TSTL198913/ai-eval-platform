# src/domain/evaluators/metadata.py

from pydantic import BaseModel


class BaseMetadata(BaseModel):
    priority: str = "normal"
    debug_mode: bool = False

class FinanceMetadata(BaseMetadata):
    rate: float = 0.0
    target: str = "general"

class CodeMetadata(BaseMetadata):
    language: str = "python"
    style_guide: str = "pep8"

class TextMetadata(BaseMetadata):
    tone: str = "neutral"
