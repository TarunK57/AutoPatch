"""AST and code intelligence data models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class SourceRange(BaseModel):
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    start_col: int = Field(ge=0, default=0)
    end_col: int = Field(ge=0, default=0)


class ClassDefinition(BaseModel):
    name: str
    file_path: str
    signature: str
    range: SourceRange
    docstring: Optional[str] = None


class FunctionDefinition(BaseModel):
    name: str
    file_path: str
    signature: str
    implementation: str
    range: SourceRange
    docstring: Optional[str] = None


class MethodDefinition(BaseModel):
    name: str
    class_name: str
    file_path: str
    signature: str
    implementation: str
    range: SourceRange
    docstring: Optional[str] = None


class ImportDefinition(BaseModel):
    file_path: str
    module: str
    imported_names: List[str] = Field(default_factory=list)
    line: int = Field(ge=1)


class FileASTIndex(BaseModel):
    file_path: str
    language: str
    classes: List[ClassDefinition] = Field(default_factory=list)
    functions: List[FunctionDefinition] = Field(default_factory=list)
    methods: List[MethodDefinition] = Field(default_factory=list)
    imports: List[ImportDefinition] = Field(default_factory=list)


class SearchResult(BaseModel):
    file_path: str
    symbol_name: str
    symbol_type: str  # "class", "method", "function", "code"
    content: str
    line_start: int
    line_end: int
