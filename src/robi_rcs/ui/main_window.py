from __future__ import annotations

import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QWidget,
)

from robi_rcs.models import ProjectModel
from robi_rcs.services.backend import (
    create_mesh_plan,
    create_synthetic_result,
    load_geometry,
    prepare_openems_job,
    run_openems_job,
)
from robi_rcs.services.diagnostics import (
    build_preflight_report,
    format_preflight_report,
    format_runtime_status,
    inspect_openems_backend,
    inspect_runtime_status,
)
from robi_rcs.services.export_service import export_report_bundle, load_project, save_project
from robi_rcs.services.runtime_env import prepare_openems_runtime
from robi_rcs.ui.widgets import LogPanel, ParameterPanel, PreviewPanel, ResultsPanel


class SimulationWorker(QObject):
    progress = Signal(int, str)
    log = Signal(str, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, project: ProjectModel, mesh, geometry_info, mesh_plan) -> None:
        super().__init__()
        self.project = project
        self.mesh = mesh
        self.geometry_info = geometry_info
        self.mesh_plan = mesh_plan

    def run(self) -> None:
        try:
            self.progress.emit(15, "Job előkészítés")
            self.log.emit("INFO", "openEMS job könyvtár előkészítése")
            run_dir = prepare_openems_job(self.project, self.mesh, self.geometry_info, self.mesh_plan)
            self.progress.emit(35, "Solver környezet ellenőrzése")
            backend_status = inspect_openems_backend(self.project.solver.openems_python_command)
            for detail in backend_status.details[:2]:
                self.log.emit("INFO" if backend_status.available else "WARNING", detail)
            if self.project.solver.setup_only:
                self.log.emit("INFO", "Csak input generálás történt, solver futtatás nélkül.")
                self.progress.emit(60, "Input generálva")
                result = create_synthetic_result(self.mesh, self.geometry_info, self.project)
                result.messages.insert(0, f"openEMS input előállítva: {run_dir}")
            elif self.project.solver.openems_python_command.strip():
                if not backend_status.available:
                    raise RuntimeError("A megadott openEMS Python környezet nem importálja egyszerre az openEMS és CSXCAD modulokat.")
                self.log.emit("INFO", "Külső openEMS Python környezet használata")
                self.progress.emit(55, "openEMS futtatás")
                result = run_openems_job(self.project, run_dir, python_command=backend_status.executable)
            elif backend_status.available:
                self.log.emit("INFO", "Bundled openEMS Python környezet használata")
                self.progress.emit(55, "openEMS futtatás")
                result = run_openems_job(self.project, run_dir, python_command=backend_status.executable)
            else:
                self.log.emit("WARNING", "openEMS környezet nincs megadva, szintetikus eredmény készül")
                self.progress.emit(55, "Szintetikus eredmény generálása")
                result = create_synthetic_result(self.mesh, self.geometry_info, self.project)
            result.run_directory = str(run_dir)
            self.progress.emit(100, "Kész")
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        prepare_openems_runtime()
        self.setWindowTitle("Robi RCS")
        self.resize(1700, 980)

        self.parameter_panel = ParameterPanel()
        self.preview_panel = PreviewPanel("Állandó preview")
        self.results_panel = ResultsPanel()
        self.log_panel = LogPanel()

        self.current_project = ProjectModel()
        self.current_mesh = None
        self.current_geometry_info = None
        self.current_mesh_plan = None
        self.current_result = None
        self.current_preflight_report = None
        self.current_runtime_status = None
        self.worker_thread: QThread | None = None

        backend_status = inspect_openems_backend("")
        if backend_status.available:
            self.current_project.solver.openems_python_command = backend_status.executable or sys.executable

        self._build_layout()
        self._build_actions()
        self.parameter_panel.apply_project(self.current_project)
        self.parameter_panel.openems_python.editingFinished.connect(self._refresh_runtime_status)
        self._refresh_runtime_status()

    def _build_layout(self) -> None:
        horizontal = QSplitter()
        left = QSplitter()
        left.setOrientation(Qt.Orientation.Vertical)
        left.addWidget(self.preview_panel)
        left.addWidget(self.parameter_panel)
        left.setSizes([520, 420])

        vertical = QSplitter()
        vertical.setOrientation(Qt.Orientation.Vertical)
        vertical.addWidget(self.results_panel)
        vertical.addWidget(self.log_panel)
        vertical.setSizes([760, 200])

        horizontal.addWidget(left)
        horizontal.addWidget(vertical)
        horizontal.setSizes([520, 1180])
        self.setCentralWidget(horizontal)

    def _build_actions(self) -> None:
        toolbar = self.addToolBar("Main")
        actions = [
            ("Geometria betöltése", self.load_geometry_file),
            ("Projekt mentése", self.save_project_file),
            ("Projekt betöltése", self.load_project_file),
            ("Környezet ellenőrzése", self.check_installation_status),
            ("Diagnosztika", self.run_diagnostics),
            ("Szimuláció indítása", self.run_simulation),
            ("Eredmények exportálása", self.export_results),
            ("Animáció exportálása", self.export_animation),
        ]
        for title, callback in actions:
            action = QAction(title, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)

    def load_geometry_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "3D geometria kiválasztása",
            str(Path.cwd()),
            "3D files (*.stl *.obj *.off *.ply *.step *.stp)",
        )
        if not path:
            return
        self.parameter_panel.set_geometry_path(path)
        self.current_project = self.parameter_panel.project()
        try:
            mesh, geometry_info = load_geometry(self.current_project)
        except Exception as exc:
            self._error(str(exc))
            return
        self.current_mesh = mesh
        self.current_geometry_info = geometry_info
        self.preview_panel.set_mesh(mesh, geometry_info)
        self.results_panel.show_geometry(mesh, geometry_info)
        self.log_panel.append("INFO", f"Geometria betöltve: {Path(path).name}")
        self.results_panel.append_log_copy(f"[INFO] Geometria betöltve: {Path(path).name}")
        self._update_mesh_plan()
        self._run_diagnostics(silent=True)

    def save_project_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Projekt mentése", str(Path.cwd() / "project.rcsproj"), "RCS Project (*.rcsproj)")
        if not path:
            return
        self.current_project = self.parameter_panel.project()
        saved = save_project(self.current_project, path)
        self.log_panel.append("INFO", f"Projekt mentve: {saved}")

    def load_project_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Projekt betöltése", str(Path.cwd()), "RCS Project (*.rcsproj)")
        if not path:
            return
        try:
            self.current_project = load_project(path)
            self.parameter_panel.apply_project(self.current_project)
            self.log_panel.append("INFO", f"Projekt betöltve: {Path(path).name}")
            if self.current_project.geometry.file_path:
                mesh, geometry_info = load_geometry(self.current_project)
                self.current_mesh = mesh
                self.current_geometry_info = geometry_info
                self.preview_panel.set_mesh(mesh, geometry_info)
                self.results_panel.show_geometry(mesh, geometry_info)
                self._update_mesh_plan()
                self._run_diagnostics(silent=True)
            self._refresh_runtime_status()
        except Exception as exc:
            self._error(str(exc))

    def run_diagnostics(self, _checked: bool = False) -> None:
        self._run_diagnostics(silent=False)

    def check_installation_status(self, _checked: bool = False) -> None:
        self._refresh_runtime_status(show_dialog=True, log_result=True)

    def run_simulation(self) -> None:
        self.current_project = self.parameter_panel.project()
        if not self.current_project.geometry.file_path:
            self._error("Előbb válassz 3D geometriát.")
            return
        try:
            if self.current_mesh is None or self.current_geometry_info is None:
                self.current_mesh, self.current_geometry_info = load_geometry(self.current_project)
            self._update_mesh_plan()
        except Exception as exc:
            self._error(str(exc))
            return
        if not self._run_diagnostics(silent=False):
            return

        self.log_panel.set_status("Szimuláció indul", 0)
        self.log_panel.append("INFO", "Szimuláció indítása")
        self.results_panel.append_log_copy("[INFO] Szimuláció indítása")

        worker = SimulationWorker(self.current_project, self.current_mesh, self.current_geometry_info, self.current_mesh_plan)
        thread = QThread(self)
        worker.moveToThread(thread)
        worker.progress.connect(self._on_progress)
        worker.log.connect(self._on_worker_log)
        worker.finished.connect(self._on_simulation_finished)
        worker.failed.connect(self._on_simulation_failed)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        self.worker_thread = thread
        thread.start()

    def export_results(self) -> None:
        if self.current_result is None:
            self._error("Nincs exportálható eredmény.")
            return
        self.current_project = self.parameter_panel.project()
        output_dir = Path(self.parameter_panel.output_dir.text().strip() or "exports")
        exported = export_report_bundle(
            output_dir,
            self.current_project,
            self.current_result,
            mesh=self.current_mesh,
            geometry_info=self.current_geometry_info,
            mesh_plan=self.current_mesh_plan,
            preflight_report=self.current_preflight_report,
        )
        exported.extend(self.results_panel.export_visuals(output_dir / "plots"))
        self.log_panel.append("INFO", f"Exportált fájlok: {len(exported)}")

    def export_animation(self) -> None:
        if self.current_result is None or not self.current_result.field_frames_2d:
            self._error("Nincs exportálható animáció.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Animáció exportálása",
            str(Path.cwd() / "animation.gif"),
            "Animations (*.gif *.mp4)",
        )
        if not path:
            return
        frames = []
        width, height = self.current_result.field_frames_shape_2d
        for frame in self.current_result.field_frames_2d:
            arr = np.array(frame, dtype=float).reshape((width, height))
            normalized = (255 * (arr - arr.min()) / max(np.ptp(arr), 1e-9)).astype("uint8")
            if Path(path).suffix.lower() == ".mp4":
                normalized = np.repeat(normalized[:, :, None], 3, axis=2)
            frames.append(normalized)
        try:
            imageio.mimsave(path, frames, fps=self.current_project.export.animation_fps)
        except Exception as exc:
            self._error(f"Animáció export hiba: {exc}")
            return
        self.log_panel.append("INFO", f"Animáció exportálva: {path}")

    def _update_mesh_plan(self) -> None:
        self.current_project = self.parameter_panel.project()
        if self.current_mesh is None or self.current_geometry_info is None:
            return
        self.current_mesh_plan = create_mesh_plan(self.current_project, self.current_geometry_info)
        self.results_panel.show_mesh_plan(self.current_geometry_info, self.current_mesh_plan)
        summary = (
            f"RAM: {self.current_mesh_plan.estimated_memory_gb:.2f} GB | "
            f"Idő: {self.current_mesh_plan.estimated_runtime_minutes:.1f} perc | "
            f"Cellák: {self.current_mesh_plan.total_cells:,}"
        )
        self.log_panel.set_summary(summary)
        for warning in self.current_mesh_plan.warnings:
            self.log_panel.append("WARNING", warning)
            self.results_panel.append_log_copy(f"[WARNING] {warning}")

    def _run_diagnostics(self, silent: bool) -> bool:
        self.current_project = self.parameter_panel.project()
        if self.current_geometry_info is None or self.current_mesh_plan is None:
            if not silent:
                self._error("A diagnosztikához előbb tölts be geometriát.")
            return False

        runtime_status = self._refresh_runtime_status()
        backend_status = runtime_status.backend_status
        self.current_preflight_report = build_preflight_report(
            self.current_project,
            self.current_geometry_info,
            self.current_mesh_plan,
            backend_status,
        )
        self.results_panel.show_preflight(format_preflight_report(self.current_preflight_report, self.current_mesh_plan))

        if not silent:
            self.log_panel.append("INFO", f"Preflight confidence: {self.current_preflight_report.confidence_label}")
            for item in self.current_preflight_report.warnings:
                self.log_panel.append(item.severity, item.summary)
                self.results_panel.append_log_copy(f"[{item.severity}] {item.summary}")
            for item in self.current_preflight_report.issues:
                self.log_panel.append(item.severity, item.summary)
                self.results_panel.append_log_copy(f"[{item.severity}] {item.summary}")

        if self.current_preflight_report.issues:
            self.log_panel.set_status("Preflight hiba", 0)
            self.log_panel.set_summary(self.current_preflight_report.issues[0].summary)
            if not silent:
                self._error("\n".join(item.summary for item in self.current_preflight_report.issues[:3]))
            return False
        return True

    def _refresh_runtime_status(self, show_dialog: bool = False, log_result: bool = False):
        self.current_project = self.parameter_panel.project()
        runtime_status = inspect_runtime_status(self.current_project.solver.openems_python_command)
        self.current_runtime_status = runtime_status

        if runtime_status.openems_ready and runtime_status.backend_status.executable and not self.current_project.solver.openems_python_command.strip():
            self.current_project.solver.openems_python_command = runtime_status.backend_status.executable
            self.parameter_panel.openems_python.setText(runtime_status.backend_status.executable)

        details = [
            f"GUI környezet: {'rendben' if runtime_status.ui_ready else 'hiányos'}",
            f"openEMS backend: {'használható' if runtime_status.openems_ready else 'nem használható'}",
        ]
        if runtime_status.backend_status.executable:
            details.append(f"Solver Python: {runtime_status.backend_status.executable}")
        details.extend(runtime_status.notes[:2])

        self.parameter_panel.set_installation_status(
            runtime_status.summary,
            details,
            runtime_status.overall_ready,
            runtime_status.ui_ready,
            runtime_status.openems_ready,
        )
        self.results_panel.show_installation_status(format_runtime_status(runtime_status))

        if log_result:
            level = "INFO" if runtime_status.overall_ready else "WARNING"
            self.log_panel.append(level, runtime_status.summary)
            self.results_panel.append_log_copy(f"[{level}] {runtime_status.summary}")

        if show_dialog:
            if runtime_status.overall_ready:
                QMessageBox.information(self, "Rendszer állapot", format_runtime_status(runtime_status))
            else:
                QMessageBox.warning(self, "Rendszer állapot", format_runtime_status(runtime_status))
        return runtime_status

    def _on_progress(self, value: int, message: str) -> None:
        self.log_panel.set_status(message, value)

    def _on_worker_log(self, level: str, message: str) -> None:
        self.log_panel.append(level, message)
        self.results_panel.append_log_copy(f"[{level}] {message}")

    def _on_simulation_finished(self, result) -> None:
        self.current_result = result
        self.results_panel.show_result(self.current_mesh, self.current_geometry_info, result)
        for message in result.messages:
            level = "WARNING" if result.synthetic else "INFO"
            self.log_panel.append(level, message)
            self.results_panel.append_log_copy(f"[{level}] {message}")
        if result.run_directory:
            self.log_panel.append("INFO", f"Run directory: {result.run_directory}")
        self.log_panel.set_status("Szimuláció kész", 100)
        self.log_panel.set_summary(
            f"Eredmények elkészültek. Forrás: {'szintetikus' if result.synthetic else 'openEMS'} | Frekvenciapontok: {len(result.frequencies_hz)}"
        )

    def _on_simulation_failed(self, message: str) -> None:
        self._error(message)
        self.log_panel.set_status("Hiba", 0)
        self.log_panel.append("ERROR", message)
        self.results_panel.append_log_copy(f"[ERROR] {message}")

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "Hiba", message)
