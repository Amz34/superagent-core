import unittest
import os
import shutil
import tempfile
from superagent_core.tools import ToolRegistry, ToolResult, SafeMathEvaluator

class TestTools(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.registry = ToolRegistry(sandbox_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_calc(self):
        evaluator = SafeMathEvaluator()
        self.assertEqual(evaluator.evaluate("1 + 2 * 3"), 7)
        self.assertEqual(evaluator.evaluate("(10 - 2) / 4"), 2)
        self.assertEqual(evaluator.evaluate("2**3"), 8)
        with self.assertRaises(ValueError):
            evaluator.evaluate("__import__('math').sqrt(4)")

    def test_file_tools(self):
        # Write
        res = self.registry.execute("file_write", path="test.txt", content="hello world")
        self.assertTrue(res.success)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "test.txt")))

        # Read
        res = self.registry.execute("file_read", path="test.txt")
        self.assertTrue(res.success)
        self.assertEqual(res.output, "hello world")

    def test_sandbox_escape(self):
        res = self.registry.execute("file_write", path="../escape.txt", content="hack")
        self.assertFalse(res.success)
        self.assertIn("PermissionError", res.error)

    def test_regex_extract(self):
        res = self.registry.execute("regex_extract", text="order ID: 12345", pattern=r"ID: (\d+)")
        self.assertTrue(res.success)
        self.assertEqual(res.output, "['12345']")

    def test_system_probe(self):
        res = self.registry.execute("system_probe")
        self.assertTrue(res.success)
        self.assertIn("system", res.output)
