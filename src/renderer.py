"""Document renderer module (maintained collaboratively, e.g. by P22)."""

from typing import List, Union
from .model import BlockNode, ParseResult


class Renderer:
    """Renders a ParseResult or list of BlockNodes into formatted HTML."""

    def render(self, parsed: Union[ParseResult, List[BlockNode]]) -> str:
        nodes = parsed.nodes if isinstance(parsed, ParseResult) else parsed
        lines = [self._render_node(node) for node in nodes]
        return "\n".join(lines)

    def _render_node(self, node: BlockNode) -> str:
        cls_attr = f' class="{node.style_class}"' if getattr(node, "style_class", "default") != "default" else ""
        if node.kind == "heading":
            return f"<h1{cls_attr}>{node.content}</h1>"
        if node.kind == "item":
            return f"<li{cls_attr}>{node.content}</li>"
        if node.kind == "section":
            inner = "\n".join(self._render_node(child) for child in node.children)
            if inner:
                return f'<section data-title="{node.content}"{cls_attr}>\n{inner}\n</section>'
            return f'<section data-title="{node.content}"{cls_attr}></section>'
        return f"<p{cls_attr}>{node.content}</p>"
