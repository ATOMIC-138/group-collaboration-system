import unittest
from src.parser import Parser


class TestParser(unittest.TestCase):
    def test_basic_heading_and_items(self):
        parser = Parser()
        result = parser.parse("# Welcome\n- First\n- Second\nHello world")
        self.assertEqual(len(result.nodes), 4)
        self.assertEqual(result.nodes[0].kind, "heading")
        self.assertEqual(result.nodes[0].content, "Welcome")
        self.assertEqual(result.nodes[1].kind, "item")
        self.assertEqual(result.nodes[3].kind, "paragraph")
        self.assertEqual(result.warnings, [])

    def test_nested_section_parsing(self):
        parser = Parser()
        result = parser.parse("{ intro {\n# Nested Title\n- Bullet\n}")
        self.assertEqual(len(result.nodes), 1)
        sec = result.nodes[0]
        self.assertEqual(sec.kind, "section")
        self.assertEqual(sec.content, "intro")
        self.assertEqual(len(sec.children), 2)
        self.assertEqual(sec.children[0].content, "Nested Title")


if __name__ == "__main__":
    unittest.main()
