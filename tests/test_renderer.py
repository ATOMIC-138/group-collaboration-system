import unittest
from src.parser import Parser
from src.renderer import Renderer


class TestRenderer(unittest.TestCase):
    def test_render_parse_result(self):
        parser = Parser()
        renderer = Renderer()
        parsed = parser.parse("# Header\nParagraph text\n- Item 1")
        html = renderer.render(parsed)
        self.assertIn("<h1>Header</h1>", html)
        self.assertIn("<p>Paragraph text</p>", html)
        self.assertIn("<li>Item 1</li>", html)

    def test_render_nested_section(self):
        parser = Parser()
        renderer = Renderer()
        parsed = parser.parse("{ details {\n- Subitem\n}")
        html = renderer.render(parsed)
        self.assertIn('<section data-title="details">', html)
        self.assertIn("<li>Subitem</li>", html)
        self.assertIn("</section>", html)



    def test_combined_end_column_and_style_class(self):
        parser = Parser()
        renderer = Renderer()
        parsed = parser.parse("# Combined Check")
        self.assertGreater(parsed.nodes[0].end_column, 0)
        parsed.nodes[0].style_class = "highlight"
        html = renderer.render(parsed)
        self.assertIn('<h1 class="highlight">Combined Check</h1>', html)



    def test_combined_end_column_and_style_class(self):
        parser = Parser()
        renderer = Renderer()
        parsed = parser.parse("# Combined Check")
        self.assertGreater(parsed.nodes[0].end_column, 0)
        parsed.nodes[0].style_class = "highlight"
        html = renderer.render(parsed)
        self.assertIn('<h1 class="highlight">Combined Check</h1>', html)


if __name__ == "__main__":
    unittest.main()
