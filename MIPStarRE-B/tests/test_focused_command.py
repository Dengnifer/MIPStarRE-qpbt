from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FocusedValidationCommandTests(unittest.TestCase):
    def test_documented_focused_command_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "tests/test_check_workflow.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_package_style_invocation_is_not_required(self) -> None:
        protocol = (ROOT / "protocols" / "local-development.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("python3 tests/test_check_workflow.py", protocol)
        self.assertNotIn("python3 -m unittest tests.", protocol)

        # An explicit missing module gives a deterministic nonzero result even
        # on hosts that happen to provide a third-party `tests` package.
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.__qpbt011_missing__"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
