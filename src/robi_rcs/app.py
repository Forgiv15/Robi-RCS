from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from robi_rcs.services.runtime_env import prepare_openems_runtime
from robi_rcs.ui.main_window import MainWindow


def main() -> int:
    prepare_openems_runtime()
    app = QApplication(sys.argv)
    app.setApplicationName("Robi RCS")
    window = MainWindow()
    window.show()
    return app.exec()
