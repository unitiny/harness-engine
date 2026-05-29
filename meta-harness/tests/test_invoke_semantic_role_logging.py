import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "engine" / "invoke_semantic_role.py"
SPEC = importlib.util.spec_from_file_location("invoke_semantic_role", MODULE_PATH)
invoke_semantic_role = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(invoke_semantic_role)


class SemanticRoleLoggingTests(unittest.TestCase):
    def test_stream_json_is_rendered_with_color_and_full_log(self):
        event = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "text",
                        "text": "first analysis line\nsecond analysis line\nthird analysis line",
                    }
                ]
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            console_log = Path(tmp) / "console.log"
            old_force_color = os.environ.get("FORCE_COLOR")
            os.environ["FORCE_COLOR"] = "1"
            try:
                output = io.StringIO()
                with redirect_stdout(output):
                    invoke_semantic_role.render_agent_stream_line(
                        role_name="semantic_triage",
                        stream_name="stdout",
                        line=json.dumps(event),
                        console_log=console_log,
                    )
            finally:
                if old_force_color is None:
                    os.environ.pop("FORCE_COLOR", None)
                else:
                    os.environ["FORCE_COLOR"] = old_force_color

            visible = output.getvalue()
            stored = console_log.read_text(encoding="utf-8")

        self.assertIn("\x1b[", visible)
        self.assertIn("[AI]", visible)
        self.assertIn("third analysis line", visible)
        self.assertIn("[AI]", stored)
        self.assertIn("first analysis line", stored)
        self.assertIn("second analysis line", stored)
        self.assertIn("third analysis line", stored)


if __name__ == "__main__":
    unittest.main()
