"""Shared data structures for the Parser and Renderer."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class BlockNode:
    """Represents a parsed block node in a document."""

    kind: str
    content: str
    children: List["BlockNode"] = field(default_factory=list)
    line: int = 1
    end_column: int = 0
    style_class: str = "default"


@dataclass
class ParseResult:
    """Structured result returned by Parser.parse."""

    nodes: List[BlockNode] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_name: str = "<memory>"
