"""Document parser module (maintained collaboratively, e.g. by P17)."""

from typing import List, Union
from .model import BlockNode, ParseResult


class Parser:
    """Parses lightweight structured text into BlockNode trees wrapped in ParseResult."""

    def parse(self, text: str, source_name: str = "<memory>") -> ParseResult:
        nodes: List[BlockNode] = []
        warnings: List[str] = []
        stack: List[BlockNode] = []

        for idx, raw_line in enumerate(text.splitlines(), start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue

            if stripped.startswith("# "):
                node = BlockNode(kind="heading", content=stripped[2:].strip(), line=idx, end_column=len(raw_line))
                self._attach(nodes, stack, node)
            elif stripped.startswith("- "):
                node = BlockNode(kind="item", content=stripped[2:].strip(), line=idx, end_column=len(raw_line))
                self._attach(nodes, stack, node)
            elif stripped.startswith("{") and stripped.endswith("{"):
                title = stripped[:-1].strip("{ ").strip() or "section"
                node = BlockNode(kind="section", content=title, line=idx, end_column=len(raw_line))
                self._attach(nodes, stack, node)
                stack.append(node)
            elif stripped == "}":
                if stack:
                    stack.pop()
                else:
                    warnings.append(f"Line {idx}: unmatched closing brace '}}'")
            else:
                node = BlockNode(kind="paragraph", content=stripped, line=idx, end_column=len(raw_line))
                self._attach(nodes, stack, node)

        if stack:
            warnings.append(f"Unclosed section '{stack[-1].content}' starting at line {stack[-1].line}")

        return ParseResult(nodes=nodes, warnings=warnings, source_name=source_name)

    @staticmethod
    def _attach(root_nodes: List[BlockNode], stack: List[BlockNode], node: BlockNode) -> None:
        if stack:
            stack[-1].children.append(node)
        else:
            root_nodes.append(node)
