from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from robi_rcs.services.backend import create_synthetic_result
from robi_rcs.ui.main_window import MainWindow, SimulationWorker
from robi_rcs.ui.widgets import ParameterPanel


class UiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_window_constructs_and_exports_visual_placeholders(self) -> None:
        window = MainWindow()
        self.assertIn("openEMS", window.parameter_panel.install_summary.text())
        self.assertIn("Általános állapot", window.results_panel.installation_view.toPlainText())
        window.results_panel.show_preflight("diagnostics ok")
        with tempfile.TemporaryDirectory() as temp_dir:
            exported = window.results_panel.export_visuals(temp_dir)
            self.assertTrue(exported)

    def test_parameter_panel_applies_material_and_detail_presets(self) -> None:
        panel = ParameterPanel()
        panel.material_preset.setCurrentText("RAM")
        self.assertAlmostEqual(panel.epsilon_r.value(), 2.5)
        self.assertAlmostEqual(panel.conductivity.value(), 12.0)

        panel.detail_preset.setCurrentText("fine")
        self.assertEqual(panel.cells_per_wavelength.value(), 24)
        self.assertEqual(panel.detail_level.value(), 4)

    def test_parameter_panel_keeps_custom_material_presets(self) -> None:
        panel = ParameterPanel()
        panel.custom_material_presets["TesztAnyag"] = {
            "epsilon_r": 7.5,
            "mu_r": 1.2,
            "conductivity_s_per_m": 0.3,
            "loss_tangent": 0.07,
        }
        panel._sync_material_preset_items("TesztAnyag")
        panel.material_preset.setCurrentText("TesztAnyag")

        project = panel.project()
        self.assertIn("TesztAnyag", project.material.custom_presets)
        self.assertAlmostEqual(project.material.epsilon_r, 7.5)

    def test_run_simulation_creates_result_with_worker_thread(self) -> None:
        def fake_run(worker_self: SimulationWorker) -> None:
            result = create_synthetic_result(worker_self.mesh, worker_self.geometry_info, worker_self.project)
            result.messages = ["patched worker result"]
            worker_self.finished.emit(result)

        with tempfile.TemporaryDirectory() as temp_dir:
            geometry_path = Path(temp_dir) / "sphere.stl"
            trimesh.creation.icosphere(subdivisions=1, radius=0.1).export(geometry_path)

            window = MainWindow()
            window.parameter_panel.set_geometry_path(str(geometry_path))

            with patch.object(MainWindow, "_run_diagnostics", return_value=True), patch.object(SimulationWorker, "run", fake_run):
                window.run_simulation()
                for _ in range(80):
                    self.app.processEvents()
                    time.sleep(0.01)
                    if window.current_result is not None:
                        break

            self.assertIsNotNone(window.current_result)
            self.assertIn("patched worker result", window.current_result.messages)


if __name__ == "__main__":
    unittest.main()