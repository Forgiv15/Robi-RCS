from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from robi_rcs.ui.main_window import MainWindow


class UiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_window_constructs_and_exports_visual_placeholders(self) -> None:
        window = MainWindow()
        window.results_panel.show_preflight("diagnostics ok")
        with tempfile.TemporaryDirectory() as temp_dir:
            exported = window.results_panel.export_visuals(temp_dir)
            self.assertTrue(exported)


if __name__ == "__main__":
    unittest.main()