from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pyqtgraph as pg
import pyvista as pv
from pyqtgraph.exporters import ImageExporter
from pyvistaqt import QtInteractor
from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from robi_rcs.models import MeshPlan, ProjectModel


MATERIAL_PRESETS: dict[str, dict[str, float]] = {
    "PEC": {
        "epsilon_r": 1.0,
        "mu_r": 1.0,
        "conductivity_s_per_m": 5.8e7,
        "loss_tangent": 0.0,
    },
    "Lossy Dielectric": {
        "epsilon_r": 4.2,
        "mu_r": 1.0,
        "conductivity_s_per_m": 0.02,
        "loss_tangent": 0.02,
    },
    "Good Conductor": {
        "epsilon_r": 1.0,
        "mu_r": 1.0,
        "conductivity_s_per_m": 1.0e6,
        "loss_tangent": 0.0,
    },
    "RAM": {
        "epsilon_r": 2.5,
        "mu_r": 1.0,
        "conductivity_s_per_m": 12.0,
        "loss_tangent": 0.12,
    },
    "Custom Isotropic": {
        "epsilon_r": 1.0,
        "mu_r": 1.0,
        "conductivity_s_per_m": 0.0,
        "loss_tangent": 0.0,
    },
}

DETAIL_PRESET_VALUES: dict[str, tuple[int, int]] = {
    "coarse": (12, 2),
    "normal": (18, 3),
    "fine": (24, 4),
    "expert": (30, 5),
}


def _build_viewer_or_placeholder(parent: QWidget, message: str) -> tuple[QWidget, QtInteractor | None]:
    if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
        placeholder = QLabel(message)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        placeholder.setFrameShape(QFrame.Shape.StyledPanel)
        return placeholder, None
    try:
        viewer = QtInteractor(parent)
        viewer.add_axes()
        viewer.set_background("#0f1720")
        return viewer, viewer
    except Exception:
        placeholder = QLabel(message)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        placeholder.setFrameShape(QFrame.Shape.StyledPanel)
        return placeholder, None


class LogPanel(QWidget):
    cancelRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.status_label = QLabel("Idle")
        self.cancel_button = QPushButton("Szimulacio megszakitasa")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.summary_label = QLabel("Numerikus összefoglaló még nincs.")
        self.summary_label.setWordWrap(True)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        header.addWidget(self.status_label, 1)
        header.addWidget(self.cancel_button)
        layout.addLayout(header)
        layout.addWidget(self.progress)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.log_view, 1)

    def append(self, level: str, message: str) -> None:
        self.log_view.appendPlainText(f"[{level}] {message}")

    def set_status(self, message: str, progress: int | None = None) -> None:
        self.status_label.setText(message)
        if progress is not None:
            self.progress.setValue(progress)

    def set_summary(self, text: str) -> None:
        self.summary_label.setText(text)

    def set_running_state(self, running: bool) -> None:
        self.cancel_button.setEnabled(running)


class PreviewPanel(QWidget):
    def __init__(self, title: str = "Geometry Preview", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_widget, self.viewer = _build_viewer_or_placeholder(self, "3D nézet nem inicializálható ebben a környezetben.")
        self.info = QLabel("Nincs betöltött geometria.")
        self.info.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.viewer_widget, 1)
        layout.addWidget(self.info)
        self._polydata: pv.PolyData | None = None
        self._actor = None

    def set_mesh(self, mesh, geometry_info, project: ProjectModel | None = None, scalars: np.ndarray | None = None, scalar_name: str = "surface") -> None:
        if self.viewer is None:
            fallback_text = ["3D OpenGL nézet nem elérhető, de a geometria sikeresen be lett töltve."]
            if project is not None:
                fallback_text.append(f"Beeses: az={project.excitation.azimuth_deg:.1f} deg, el={project.excitation.elevation_deg:.1f} deg")
            self.info.setText("\n".join(fallback_text))
            return
        self.viewer.clear()
        self.viewer.add_axes()
        faces = np.hstack([np.full((len(mesh.faces), 1), 3), mesh.faces]).astype(np.int64).ravel()
        poly = pv.PolyData(mesh.vertices, faces)
        self._polydata = poly
        kwargs = {"color": "#8fb9ff", "smooth_shading": True, "show_edges": False}
        if scalars is not None and len(scalars) == poly.n_cells:
            poly.cell_data[scalar_name] = scalars
            kwargs = {
                "scalars": scalar_name,
                "cmap": "viridis",
                "show_edges": False,
                "smooth_shading": True,
                "scalar_bar_args": {"title": scalar_name},
            }
        self._actor = self.viewer.add_mesh(poly, **kwargs)
        self.viewer.add_bounding_box(color="#cbd5e1")
        if project is not None:
            self._add_incident_arrow(geometry_info, project)
        self.viewer.reset_camera()
        info_lines = [
            f"Fájlformátum: {geometry_info.file_format.upper()}",
            f"Kiterjedés [m]: {geometry_info.extents_m[0]:.4g} x {geometry_info.extents_m[1]:.4g} x {geometry_info.extents_m[2]:.4g}",
            f"Háromszögek: {geometry_info.triangle_count}",
            f"Watertight: {'igen' if geometry_info.watertight else 'nem'}",
            f"Felület [m²]: {geometry_info.surface_area_m2:.4g}",
        ]
        if project is not None:
            info_lines.append(f"Beeses: az={project.excitation.azimuth_deg:.1f} deg, el={project.excitation.elevation_deg:.1f} deg")
        self.info.setText("\n".join(info_lines))

    def show_mesh_plan(self, geometry_info, mesh_plan: MeshPlan, project: ProjectModel | None = None) -> None:
        if self.viewer is None:
            self.info.setText("A mesh terv elkészült, de a 3D megjelenítés ebben a környezetben nem érhető el.")
            return
        self.viewer.clear()
        self.viewer.add_axes()
        domain = pv.Cube(center=geometry_info.center_m, x_length=mesh_plan.domain_size_m[0], y_length=mesh_plan.domain_size_m[1], z_length=mesh_plan.domain_size_m[2])
        bbox = pv.Cube(center=geometry_info.center_m, x_length=geometry_info.extents_m[0], y_length=geometry_info.extents_m[1], z_length=geometry_info.extents_m[2])
        self.viewer.add_mesh(domain, style="wireframe", color="#f59e0b", line_width=1)
        self.viewer.add_mesh(bbox, style="wireframe", color="#38bdf8", line_width=2)
        if project is not None:
            self._add_incident_arrow(geometry_info, project)
        self.viewer.reset_camera()
        info_lines = [
            f"Alap cellaméret [m]: {mesh_plan.base_cell_size_m:.4g}",
            f"Cellák: {mesh_plan.cells_xyz[0]} x {mesh_plan.cells_xyz[1]} x {mesh_plan.cells_xyz[2]}",
            f"Összes cella: {mesh_plan.total_cells:,}",
            f"RAM becslés [GB]: {mesh_plan.estimated_memory_gb:.2f}",
            f"Idő becslés [perc]: {mesh_plan.estimated_runtime_minutes:.1f}",
            f"Minőség: {mesh_plan.quality_label}",
        ]
        if project is not None:
            info_lines.append(f"Beeses: az={project.excitation.azimuth_deg:.1f} deg, el={project.excitation.elevation_deg:.1f} deg")
        self.info.setText("\n".join(info_lines))

    def _add_incident_arrow(self, geometry_info, project: ProjectModel) -> None:
        if self.viewer is None:
            return
        direction = self._incident_direction(project)
        length = max(max(geometry_info.extents_m) * 0.85, mesh_safe_length(geometry_info))
        start = np.array(geometry_info.center_m, dtype=float) - direction * length * 1.2
        try:
            self.viewer.add_arrows(start[None, :], direction[None, :], mag=length, color="#ef4444")
        except Exception:
            arrow = pv.Arrow(start=start, direction=direction, scale=length)
            self.viewer.add_mesh(arrow, color="#ef4444")

    def _incident_direction(self, project: ProjectModel) -> np.ndarray:
        az = math.radians(project.excitation.azimuth_deg)
        el = math.radians(project.excitation.elevation_deg)
        direction = np.array([
            math.cos(el) * math.cos(az),
            math.cos(el) * math.sin(az),
            math.sin(el),
        ])
        norm = np.linalg.norm(direction)
        if norm <= 0.0:
            return np.array([1.0, 0.0, 0.0])
        return direction / norm


def mesh_safe_length(geometry_info) -> float:
    return max(max(geometry_info.extents_m), 1.0e-3)


class Animation2DWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.image_view = pg.ImageView()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.play_button = QPushButton("Lejátszás")
        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.slider, 1)
        layout.addWidget(self.image_view, 1)
        layout.addLayout(controls)
        self.frames: list[np.ndarray] = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next_frame)
        self.play_button.clicked.connect(self._toggle)
        self.slider.valueChanged.connect(self._show_frame)

    def set_frames(self, frames: list[np.ndarray]) -> None:
        self.frames = frames
        maximum = max(len(frames) - 1, 0)
        self.slider.setRange(0, maximum)
        if frames:
            self.image_view.setImage(frames[0].T)

    def _toggle(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.play_button.setText("Lejátszás")
            return
        if self.frames:
            self.timer.start(60)
            self.play_button.setText("Szünet")

    def _next_frame(self) -> None:
        if not self.frames:
            return
        self.slider.setValue((self.slider.value() + 1) % len(self.frames))

    def _show_frame(self, index: int) -> None:
        if self.frames:
            self.image_view.setImage(self.frames[index].T, autoLevels=False)


class Animation3DWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.viewer_widget, self.viewer = _build_viewer_or_placeholder(self, "3D animáció nem elérhető ebben a környezetben.")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.play_button = QPushButton("Lejátszás")
        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.slider, 1)
        layout.addWidget(self.viewer_widget, 1)
        layout.addLayout(controls)
        if self.viewer is not None:
            self.viewer.set_background("#101418")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next_frame)
        self.play_button.clicked.connect(self._toggle)
        self.slider.valueChanged.connect(self._show_frame)
        self.frames: list[pv.ImageData] = []
        self._actor = None

    def set_frames(self, frames: list[pv.ImageData]) -> None:
        self.frames = frames
        self.slider.setRange(0, max(len(frames) - 1, 0))
        if self.viewer is None:
            return
        self.viewer.clear()
        self.viewer.add_axes()
        if frames:
            self._actor = self.viewer.add_volume(frames[0], scalars="field", cmap="coolwarm", opacity="linear")

    def _toggle(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.play_button.setText("Lejátszás")
            return
        if self.frames:
            self.timer.start(120)
            self.play_button.setText("Szünet")

    def _next_frame(self) -> None:
        if self.frames:
            self.slider.setValue((self.slider.value() + 1) % len(self.frames))

    def _show_frame(self, index: int) -> None:
        if not self.frames or self.viewer is None:
            return
        self.viewer.clear()
        self.viewer.add_axes()
        self._actor = self.viewer.add_volume(self.frames[index], scalars="field", cmap="coolwarm", opacity="linear")


class ResultsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.geometry_preview = PreviewPanel("Geometry")
        self.mesh_preview = PreviewPanel("Mesh / Domain")
        self.installation_view = QTextEdit()
        self.installation_view.setReadOnly(True)
        self.runtime_summary = QTextEdit()
        self.runtime_summary.setReadOnly(True)
        self.rcs_plot = pg.PlotWidget()
        self.pol_plot = pg.PlotWidget()
        self.surface_preview = PreviewPanel("3D Surface Map")
        self.anim_2d = Animation2DWidget()
        self.anim_3d = Animation3DWidget()
        self.diagnostics_view = QTextEdit()
        self.diagnostics_view.setReadOnly(True)
        self.export_notes = QTextEdit()
        self.export_notes.setReadOnly(True)
        self.logs_copy = QTextEdit()
        self.logs_copy.setReadOnly(True)

        self.rcs_plot.addLegend()
        self.rcs_plot.showGrid(x=True, y=True)
        self.rcs_plot.setLabel("bottom", "Frequency", "Hz")
        self.rcs_plot.setLabel("left", "RCS", "m²")
        self.pol_plot.addLegend()
        self.pol_plot.showGrid(x=True, y=True)
        self.pol_plot.setLabel("bottom", "Azimuth", "deg")
        self.pol_plot.setLabel("left", "Angular RCS", "m²")

        self.tabs.addTab(self.geometry_preview, "Geometria")
        self.tabs.addTab(self.mesh_preview, "Mesh")
        self.tabs.addTab(self.installation_view, "Környezet")
        self.tabs.addTab(self.runtime_summary, "Futási állapot")
        self.tabs.addTab(self.rcs_plot, "RCS vs frekvencia")
        self.tabs.addTab(self.pol_plot, "Polarizáció")
        self.tabs.addTab(self.surface_preview, "3D RCS térkép")
        self.tabs.addTab(self.anim_2d, "2D animáció")
        self.tabs.addTab(self.anim_3d, "3D animáció")
        self.tabs.addTab(self.diagnostics_view, "Diagnosztika")
        self.tabs.addTab(self.export_notes, "Exportálás")
        self.tabs.addTab(self.logs_copy, "Napló/Hibák")

    def show_geometry(self, mesh, geometry_info, project: ProjectModel | None = None) -> None:
        self.geometry_preview.set_mesh(mesh, geometry_info, project=project)

    def show_mesh_plan(self, geometry_info, mesh_plan: MeshPlan, project: ProjectModel | None = None) -> None:
        self.mesh_preview.show_mesh_plan(geometry_info, mesh_plan, project=project)
        warning_text = "\n".join(mesh_plan.warnings) if mesh_plan.warnings else "Nincs kritikus figyelmeztetés."
        self.runtime_summary.setPlainText(
            "\n".join(
                [
                    f"Minimális hullámhossz [m]: {mesh_plan.lambda_min_m:.5g}",
                    f"Alap cellaméret [m]: {mesh_plan.base_cell_size_m:.5g}",
                    f"CFL időlépés [s]: {mesh_plan.estimated_timestep_s:.3e}",
                    f"Becsült timestep szám: {mesh_plan.estimated_timesteps:,}",
                    f"Becsült memória [GB]: {mesh_plan.estimated_memory_gb:.2f}",
                    f"Becsült futásidő [perc]: {mesh_plan.estimated_runtime_minutes:.1f}",
                    f"Minősítés: {mesh_plan.quality_label}",
                    "",
                    "Figyelmeztetések:",
                    warning_text,
                ]
            )
        )

    def show_installation_status(self, text: str) -> None:
        self.installation_view.setPlainText(text)

    def show_result(self, mesh, geometry_info, result, project: ProjectModel | None = None) -> None:
        self.rcs_plot.clear()
        self.rcs_plot.addLegend()
        self.rcs_plot.plot(result.frequencies_hz, result.rcs_m2, pen=pg.mkPen("#38bdf8", width=2), name="RCS total")
        self.rcs_plot.plot(result.frequencies_hz, result.copol_m2, pen=pg.mkPen("#22c55e", width=2), name="Co-pol")
        self.rcs_plot.plot(result.frequencies_hz, result.crosspol_m2, pen=pg.mkPen("#f59e0b", width=2), name="Cross-pol")

        self.pol_plot.clear()
        self.pol_plot.addLegend()
        self.pol_plot.plot(result.angular_phi_deg, result.angular_rcs_m2, pen=pg.mkPen("#e879f9", width=2), name="Angular cut")

        scalars = np.array(result.surface_intensity, dtype=float) if result.surface_intensity else None
        self.surface_preview.set_mesh(mesh, geometry_info, project=project, scalars=scalars, scalar_name="surface_proxy")
        self._set_animation_frames(result)
        synthetic_label = "szintetikus preview" if result.synthetic else "openEMS solver eredmény"
        self.export_notes.setPlainText(
            "\n".join(
                [
                    f"Eredményforrás: {synthetic_label}",
                    "Grafikon export: PNG, CSV, JSON, HDF5 a menüből.",
                    "Animáció export: GIF beépítve, MP4 csak ffmpeg esetén.",
                ]
            )
        )

    def show_preflight(self, text: str) -> None:
        self.diagnostics_view.setPlainText(text)

    def append_log_copy(self, message: str) -> None:
        self.logs_copy.append(message)

    def export_visuals(self, output_dir: str | Path) -> list[Path]:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        exported: list[Path] = []

        for file_name, plot in (("rcs_vs_frequency.png", self.rcs_plot), ("angular_rcs.png", self.pol_plot)):
            image_path = target_dir / file_name
            exporter = ImageExporter(plot.plotItem)
            exporter.parameters()["width"] = 1600
            exporter.export(str(image_path))
            exported.append(image_path)

        for preview, file_name in (
            (self.geometry_preview, "geometry_preview.png"),
            (self.mesh_preview, "mesh_preview.png"),
            (self.surface_preview, "surface_proxy.png"),
        ):
            if preview.viewer is not None:
                image_path = target_dir / file_name
                preview.viewer.screenshot(str(image_path))
                exported.append(image_path)

        text_exports = {
            "installation_status.txt": self.installation_view.toPlainText(),
            "runtime_summary.txt": self.runtime_summary.toPlainText(),
            "diagnostics.txt": self.diagnostics_view.toPlainText(),
            "export_notes.txt": self.export_notes.toPlainText(),
            "log_copy.txt": self.logs_copy.toPlainText(),
        }
        for file_name, content in text_exports.items():
            text_path = target_dir / file_name
            text_path.write_text(content, encoding="utf-8")
            exported.append(text_path)
        return exported

    def _set_animation_frames(self, result) -> None:
        frames_2d = [np.array(frame, dtype=float).reshape(result.field_frames_shape_2d) for frame in result.field_frames_2d]
        self.anim_2d.set_frames(frames_2d)
        frames_3d = []
        for frame in result.field_frames_3d:
            arr = np.array(frame, dtype=float).reshape(result.field_frames_shape_3d)
            img = pv.ImageData(dimensions=np.array(arr.shape) + 1)
            img.cell_data["field"] = arr.ravel(order="F")
            frames_3d.append(img)
        self.anim_3d.set_frames(frames_3d)


class ParameterPanel(QWidget):
    projectChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._suspend_updates = False
        self.custom_material_presets: dict[str, dict[str, float]] = {}
        outer = QVBoxLayout(self)
        status_group = QGroupBox("Rendszer állapot")
        status_group.setMaximumHeight(72)
        status_layout = QVBoxLayout(status_group)
        self.install_summary = QLabel("Telepítési állapot ellenőrzése...")
        self.install_summary.setWordWrap(True)
        self.install_detail = QLabel("")
        self.install_detail.setVisible(False)
        status_layout.addWidget(self.install_summary)
        self.toolbox = QToolBox()
        outer.addWidget(status_group)
        outer.addWidget(self.toolbox)

        self.project_name = QLineEdit("Untitled Project")
        self.description = QTextEdit()
        self.geometry_path = QLineEdit()
        self.geometry_unit = QComboBox()
        self.geometry_unit.addItems(["mm", "cm", "m"])
        self.scale = self._double_spin(0.001, 1_000_000.0, 1.0, 4)
        self.auto_repair = QCheckBox("Automatikus javítás")
        self.auto_repair.setChecked(True)

        self.material_preset = QComboBox()
        self.add_material_button = QPushButton("+ anyag")
        self.epsilon_r = self._double_spin(1.0, 1000.0, 1.0, 4)
        self.mu_r = self._double_spin(1.0, 1000.0, 1.0, 4)
        self.conductivity = self._double_spin(0.0, 1e9, 5.8e7, 2)
        self.loss_tangent = self._double_spin(0.0, 10.0, 0.0, 5)

        self.freq_start = self._double_spin(0.001, 500.0, 1.0, 4)
        self.freq_stop = self._double_spin(0.001, 500.0, 10.0, 4)
        self.freq_samples = QSpinBox()
        self.freq_samples.setRange(1, 5000)
        self.freq_samples.setValue(101)
        self.sweep_type = QComboBox()
        self.sweep_type.addItems(["linear", "logarithmic"])
        self.reference_freq = self._double_spin(0.001, 500.0, 5.0, 4)

        self.sim_mode = QComboBox()
        self.sim_mode.addItems(["monostatic", "bistatic"])
        self.azimuth = self._double_spin(-360.0, 360.0, 0.0, 2)
        self.elevation = self._double_spin(-90.0, 90.0, 0.0, 2)
        self.obs_azimuth = self._double_spin(-360.0, 360.0, 180.0, 2)
        self.obs_elevation = self._double_spin(-90.0, 90.0, 0.0, 2)
        self.polarization = QComboBox()
        self.polarization.addItems(["linear_z", "linear_x", "linear_y", "rhcp", "lhcp"])
        self.amplitude = self._double_spin(0.001, 1e6, 1.0, 4)
        self.excitation_type = QComboBox()
        self.excitation_type.addItems(["gaussian", "harmonic"])

        self.auto_mesh = QCheckBox("Automatikus mesh")
        self.auto_mesh.setChecked(True)
        self.detail_preset = QComboBox()
        self.detail_preset.addItems(["coarse", "normal", "fine", "expert"])
        self.detail_preset.setCurrentText("normal")
        self.cells_per_wavelength = QSpinBox()
        self.cells_per_wavelength.setRange(8, 64)
        self.cells_per_wavelength.setValue(20)
        self.detail_level = QSpinBox()
        self.detail_level.setRange(1, 5)
        self.detail_level.setValue(3)
        self.max_growth_ratio = self._double_spin(1.05, 2.0, 1.3, 2)
        self.target_runtime = self._double_spin(1.0, 720.0, 30.0, 1)
        self.max_memory = self._double_spin(1.0, 128.0, 12.0, 1)
        self.pml_cells = QSpinBox()
        self.pml_cells.setRange(4, 32)
        self.pml_cells.setValue(8)
        self.cfl = self._double_spin(0.1, 1.0, 0.9, 3)

        self.output_dir = QLineEdit("exports")
        self.animation_fps = QSpinBox()
        self.animation_fps.setRange(1, 120)
        self.animation_fps.setValue(20)
        self.animation_frames = QSpinBox()
        self.animation_frames.setRange(8, 240)
        self.animation_frames.setValue(48)
        self.openems_python = QLineEdit()
        self.setup_only = QCheckBox("Csak input generálás")
        self.end_criteria = self._double_spin(1.0e-9, 1.0e-2, 1.0e-5, 6)
        self.max_timesteps = QSpinBox()
        self.max_timesteps.setRange(1_000, 10_000_000)
        self.max_timesteps.setValue(100_000)
        self.threads = QSpinBox()
        self.threads.setRange(0, 64)
        self.threads.setValue(0)

        self._sync_material_preset_items()
        self._add_sections()
        self._connect_live_updates()
        self._apply_selected_material_preset(self.material_preset.currentText(), emit_change=False)
        self._apply_detail_preset(self.detail_preset.currentText(), emit_change=False)

    def _add_sections(self) -> None:
        self.toolbox.addItem(self._make_form("Projekt", [("Projekt név", self.project_name), ("Leírás", self.description)]), "Projekt")
        self.toolbox.addItem(
            self._make_form(
                "Geometria",
                [
                    ("Geometria fájl", self.geometry_path),
                    ("Mértékegység", self.geometry_unit),
                    ("Scale", self.scale),
                    ("Javítás", self.auto_repair),
                ],
            ),
            "Geometria",
        )
        self.toolbox.addItem(
            self._make_form(
                "Anyag",
                [
                    ("Preset", self._build_material_preset_row()),
                    ("Epsilon_r", self.epsilon_r),
                    ("Mu_r", self.mu_r),
                    ("Vezetőképesség [S/m]", self.conductivity),
                    ("Tan delta", self.loss_tangent),
                ],
            ),
            "Anyag",
        )
        self.toolbox.addItem(
            self._make_form(
                "Frekvencia",
                [
                    ("Start [GHz]", self.freq_start),
                    ("Stop [GHz]", self.freq_stop),
                    ("Minták", self.freq_samples),
                    ("Sweep", self.sweep_type),
                    ("Referencia [GHz]", self.reference_freq),
                ],
            ),
            "Frekvencia",
        )
        self.toolbox.addItem(
            self._make_form(
                "Gerjesztés",
                [
                    ("Mód", self.sim_mode),
                    ("Azimuth [deg]", self.azimuth),
                    ("Elevation [deg]", self.elevation),
                    ("Obs. azimuth [deg]", self.obs_azimuth),
                    ("Obs. elevation [deg]", self.obs_elevation),
                    ("Polarizáció", self.polarization),
                    ("Amplitúdó [V/m]", self.amplitude),
                    ("Gerjesztés", self.excitation_type),
                ],
            ),
            "Gerjesztés",
        )
        self.toolbox.addItem(
            self._make_form(
                "Mesh és solver",
                [
                    ("Auto mesh", self.auto_mesh),
                    ("Preset", self.detail_preset),
                    ("Cella / hullámhossz", self.cells_per_wavelength),
                    ("Részletesség 1-5", self.detail_level),
                    ("Mesh growth", self.max_growth_ratio),
                    ("Cél futásidő [perc]", self.target_runtime),
                    ("Memória limit [GB]", self.max_memory),
                    ("PML cellák", self.pml_cells),
                    ("CFL factor", self.cfl),
                    ("openEMS python", self.openems_python),
                    ("Csak input", self.setup_only),
                    ("End criteria", self.end_criteria),
                    ("Max timesteps", self.max_timesteps),
                    ("Szálak száma", self.threads),
                ],
            ),
            "Mesh / Solver",
        )
        self.toolbox.addItem(
            self._make_form(
                "Export",
                [
                    ("Output mappa", self.output_dir),
                    ("Animáció fps", self.animation_fps),
                    ("Animáció frame-ek", self.animation_frames),
                ],
            ),
            "Export",
        )

    def project(self) -> ProjectModel:
        project = ProjectModel()
        project.project_name = self.project_name.text().strip() or "Untitled Project"
        project.description = self.description.toPlainText().strip()
        project.geometry.file_path = self.geometry_path.text().strip()
        project.geometry.unit = self.geometry_unit.currentText()
        project.geometry.scale = self.scale.value()
        project.geometry.auto_repair = self.auto_repair.isChecked()
        project.material.preset = self.material_preset.currentText()
        project.material.epsilon_r = self.epsilon_r.value()
        project.material.mu_r = self.mu_r.value()
        project.material.conductivity_s_per_m = self.conductivity.value()
        project.material.loss_tangent = self.loss_tangent.value()
        project.material.custom_presets = dict(self.custom_material_presets)
        project.frequency.start_hz = self.freq_start.value() * 1e9
        project.frequency.stop_hz = self.freq_stop.value() * 1e9
        project.frequency.samples = self.freq_samples.value()
        project.frequency.sweep_type = self.sweep_type.currentText()
        project.frequency.reference_hz = self.reference_freq.value() * 1e9
        project.excitation.simulation_mode = self.sim_mode.currentText()
        project.excitation.azimuth_deg = self.azimuth.value()
        project.excitation.elevation_deg = self.elevation.value()
        project.excitation.observation_azimuth_deg = self.obs_azimuth.value()
        project.excitation.observation_elevation_deg = self.obs_elevation.value()
        project.excitation.polarization = self.polarization.currentText()
        project.excitation.amplitude_v_per_m = self.amplitude.value()
        project.excitation.excitation_type = self.excitation_type.currentText()
        project.mesh.auto_mesh = self.auto_mesh.isChecked()
        project.mesh.detail_preset = self.detail_preset.currentText()
        project.mesh.cells_per_wavelength = self.cells_per_wavelength.value()
        project.mesh.detail_level = self.detail_level.value()
        project.mesh.max_growth_ratio = self.max_growth_ratio.value()
        project.mesh.target_runtime_minutes = self.target_runtime.value()
        project.mesh.max_memory_gb = self.max_memory.value()
        project.mesh.pml_cells = self.pml_cells.value()
        project.mesh.cfl_factor = self.cfl.value()
        project.export.output_dir = self.output_dir.text().strip() or "exports"
        project.export.animation_fps = self.animation_fps.value()
        project.export.animation_frames = self.animation_frames.value()
        project.solver.openems_python_command = self.openems_python.text().strip()
        project.solver.setup_only = self.setup_only.isChecked()
        project.solver.end_criteria = self.end_criteria.value()
        project.solver.max_timesteps = self.max_timesteps.value()
        project.solver.num_threads = self.threads.value()
        return project

    def apply_project(self, project: ProjectModel) -> None:
        self._suspend_updates = True
        self.custom_material_presets = dict(project.material.custom_presets)
        self._sync_material_preset_items(project.material.preset)
        self.project_name.setText(project.project_name)
        self.description.setPlainText(project.description)
        self.geometry_path.setText(project.geometry.file_path)
        self.geometry_unit.setCurrentText(project.geometry.unit)
        self.scale.setValue(project.geometry.scale)
        self.auto_repair.setChecked(project.geometry.auto_repair)
        self.material_preset.setCurrentText(project.material.preset)
        self.epsilon_r.setValue(project.material.epsilon_r)
        self.mu_r.setValue(project.material.mu_r)
        self.conductivity.setValue(project.material.conductivity_s_per_m)
        self.loss_tangent.setValue(project.material.loss_tangent)
        self.freq_start.setValue(project.frequency.start_hz / 1e9)
        self.freq_stop.setValue(project.frequency.stop_hz / 1e9)
        self.freq_samples.setValue(project.frequency.samples)
        self.sweep_type.setCurrentText(project.frequency.sweep_type)
        self.reference_freq.setValue(project.frequency.reference_hz / 1e9)
        self.sim_mode.setCurrentText(project.excitation.simulation_mode)
        self.azimuth.setValue(project.excitation.azimuth_deg)
        self.elevation.setValue(project.excitation.elevation_deg)
        self.obs_azimuth.setValue(project.excitation.observation_azimuth_deg)
        self.obs_elevation.setValue(project.excitation.observation_elevation_deg)
        self.polarization.setCurrentText(project.excitation.polarization)
        self.amplitude.setValue(project.excitation.amplitude_v_per_m)
        self.excitation_type.setCurrentText(project.excitation.excitation_type)
        self.auto_mesh.setChecked(project.mesh.auto_mesh)
        self.detail_preset.setCurrentText(project.mesh.detail_preset)
        self.cells_per_wavelength.setValue(project.mesh.cells_per_wavelength)
        self.detail_level.setValue(project.mesh.detail_level)
        self.max_growth_ratio.setValue(project.mesh.max_growth_ratio)
        self.target_runtime.setValue(project.mesh.target_runtime_minutes)
        self.max_memory.setValue(project.mesh.max_memory_gb)
        self.pml_cells.setValue(project.mesh.pml_cells)
        self.cfl.setValue(project.mesh.cfl_factor)
        self.output_dir.setText(project.export.output_dir)
        self.animation_fps.setValue(project.export.animation_fps)
        self.animation_frames.setValue(project.export.animation_frames)
        self.openems_python.setText(project.solver.openems_python_command)
        self.setup_only.setChecked(project.solver.setup_only)
        self.end_criteria.setValue(project.solver.end_criteria)
        self.max_timesteps.setValue(project.solver.max_timesteps)
        self.threads.setValue(project.solver.num_threads)
        self._suspend_updates = False
        self._emit_project_changed()

    def set_geometry_path(self, path: str) -> None:
        self.geometry_path.setText(path)

    def set_installation_status(
        self,
        summary: str,
        details: list[str],
        overall_ready: bool,
        ui_ready: bool,
        openems_ready: bool,
    ) -> None:
        if overall_ready:
            color = "#166534"
        elif ui_ready and not openems_ready:
            color = "#b45309"
        else:
            color = "#b91c1c"
        short_summary = summary
        if openems_ready:
            short_summary += " | openEMS OK"
        elif ui_ready:
            short_summary += " | openEMS nincs keszen"
        else:
            short_summary += " | GUI csomag hianyos"
        self.install_summary.setText(short_summary)
        self.install_summary.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.install_summary.setToolTip("\n".join(details))

    def _build_material_preset_row(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.material_preset, 1)
        layout.addWidget(self.add_material_button)
        return container

    def _connect_live_updates(self) -> None:
        for line_edit in (self.project_name, self.geometry_path, self.output_dir, self.openems_python):
            line_edit.editingFinished.connect(self._emit_project_changed)
        self.description.textChanged.connect(self._emit_project_changed)
        for combo in (
            self.geometry_unit,
            self.material_preset,
            self.sweep_type,
            self.sim_mode,
            self.polarization,
            self.excitation_type,
            self.detail_preset,
        ):
            combo.currentTextChanged.connect(self._emit_project_changed)
        for checkbox in (self.auto_repair, self.auto_mesh, self.setup_only):
            checkbox.toggled.connect(self._emit_project_changed)
        for spin in (
            self.scale,
            self.epsilon_r,
            self.mu_r,
            self.conductivity,
            self.loss_tangent,
            self.freq_start,
            self.freq_stop,
            self.freq_samples,
            self.reference_freq,
            self.azimuth,
            self.elevation,
            self.obs_azimuth,
            self.obs_elevation,
            self.amplitude,
            self.cells_per_wavelength,
            self.detail_level,
            self.max_growth_ratio,
            self.target_runtime,
            self.max_memory,
            self.pml_cells,
            self.cfl,
            self.animation_fps,
            self.animation_frames,
            self.end_criteria,
            self.max_timesteps,
            self.threads,
        ):
            spin.valueChanged.connect(self._emit_project_changed)
        self.material_preset.currentTextChanged.connect(self._on_material_preset_changed)
        self.detail_preset.currentTextChanged.connect(self._on_detail_preset_changed)
        self.add_material_button.clicked.connect(self._on_add_material_preset)

    def _emit_project_changed(self) -> None:
        if not self._suspend_updates:
            self.projectChanged.emit()

    def _all_material_presets(self) -> dict[str, dict[str, float]]:
        presets = dict(MATERIAL_PRESETS)
        presets.update(self.custom_material_presets)
        return presets

    def _sync_material_preset_items(self, preferred: str | None = None) -> None:
        preferred_name = preferred or self.material_preset.currentText() or "PEC"
        with QSignalBlocker(self.material_preset):
            self.material_preset.clear()
            self.material_preset.addItems(list(self._all_material_presets().keys()))
            index = self.material_preset.findText(preferred_name)
            self.material_preset.setCurrentIndex(index if index >= 0 else 0)
        self._apply_selected_material_preset(self.material_preset.currentText(), emit_change=False)

    def _current_material_values(self) -> dict[str, float]:
        return {
            "epsilon_r": self.epsilon_r.value(),
            "mu_r": self.mu_r.value(),
            "conductivity_s_per_m": self.conductivity.value(),
            "loss_tangent": self.loss_tangent.value(),
        }

    def _on_material_preset_changed(self, preset_name: str) -> None:
        self._apply_selected_material_preset(preset_name, emit_change=True)

    def _apply_selected_material_preset(self, preset_name: str, emit_change: bool) -> None:
        values = self._all_material_presets().get(preset_name)
        if values is None:
            return
        previous_state = self._suspend_updates
        self._suspend_updates = True
        self.epsilon_r.setValue(float(values.get("epsilon_r", self.epsilon_r.value())))
        self.mu_r.setValue(float(values.get("mu_r", self.mu_r.value())))
        self.conductivity.setValue(float(values.get("conductivity_s_per_m", self.conductivity.value())))
        self.loss_tangent.setValue(float(values.get("loss_tangent", self.loss_tangent.value())))
        self._suspend_updates = previous_state
        if emit_change:
            self._emit_project_changed()

    def _on_detail_preset_changed(self, preset_name: str) -> None:
        self._apply_detail_preset(preset_name, emit_change=True)

    def _apply_detail_preset(self, preset_name: str, emit_change: bool) -> None:
        values = DETAIL_PRESET_VALUES.get(preset_name)
        if values is None:
            return
        cpw, detail_level = values
        previous_state = self._suspend_updates
        self._suspend_updates = True
        self.cells_per_wavelength.setValue(cpw)
        self.detail_level.setValue(detail_level)
        self._suspend_updates = previous_state
        if emit_change:
            self._emit_project_changed()

    def _on_add_material_preset(self) -> None:
        name, accepted = QInputDialog.getText(self, "Uj anyag preset", "Preset neve:")
        if not accepted:
            return
        preset_name = name.strip()
        if not preset_name:
            return
        self.custom_material_presets[preset_name] = self._current_material_values()
        self._sync_material_preset_items(preset_name)
        self._emit_project_changed()

    def _make_form(self, title: str, rows: list[tuple[str, QWidget]]) -> QWidget:
        container = QGroupBox(title)
        form = QFormLayout(container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for label, widget in rows:
            form.addRow(label, widget)
        return container

    def _double_spin(self, low: float, high: float, value: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(low, high)
        spin.setDecimals(decimals)
        spin.setValue(value)
        spin.setKeyboardTracking(False)
        return spin
