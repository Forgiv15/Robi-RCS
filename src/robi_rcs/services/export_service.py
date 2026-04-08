from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

import h5py
import numpy as np
import pyvista as pv

from robi_rcs.models import GeometryInfo, MeshPlan, PreflightReport, ProjectModel, SimulationResult, ensure_project_extension


def save_project(project: ProjectModel, path: str | Path) -> Path:
    target = ensure_project_extension(path)
    target.write_text(json.dumps(project.to_dict(), indent=2), encoding="utf-8")
    return target


def load_project(path: str | Path) -> ProjectModel:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ProjectModel.from_dict(data)


def export_numeric_results(base_dir: str | Path, result: SimulationResult) -> list[Path]:
    output_dir = Path(base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []

    csv_path = output_dir / "rcs_vs_frequency.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frequency_hz", "rcs_m2", "copol_m2", "crosspol_m2"])
        for row in zip(result.frequencies_hz, result.rcs_m2, result.copol_m2, result.crosspol_m2):
            writer.writerow(row)
    exported.append(csv_path)

    angular_path = output_dir / "angular_rcs.csv"
    with angular_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["phi_deg", "angular_rcs_m2"])
        for row in zip(result.angular_phi_deg, result.angular_rcs_m2):
            writer.writerow(row)
    exported.append(angular_path)

    json_path = output_dir / "result.json"
    json_path.write_text(
        json.dumps(
            {
                "frequencies_hz": result.frequencies_hz,
                "rcs_m2": result.rcs_m2,
                "copol_m2": result.copol_m2,
                "crosspol_m2": result.crosspol_m2,
                "angular_phi_deg": result.angular_phi_deg,
                "angular_rcs_m2": result.angular_rcs_m2,
                "synthetic": result.synthetic,
                "messages": result.messages,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    exported.append(json_path)

    hdf5_path = output_dir / "result.h5"
    with h5py.File(hdf5_path, "w") as handle:
        handle.create_dataset("frequencies_hz", data=result.frequencies_hz)
        handle.create_dataset("rcs_m2", data=result.rcs_m2)
        handle.create_dataset("copol_m2", data=result.copol_m2)
        handle.create_dataset("crosspol_m2", data=result.crosspol_m2)
        handle.create_dataset("angular_phi_deg", data=result.angular_phi_deg)
        handle.create_dataset("angular_rcs_m2", data=result.angular_rcs_m2)
        handle.create_dataset("surface_intensity", data=result.surface_intensity)
        handle.attrs["synthetic"] = int(result.synthetic)
    exported.append(hdf5_path)
    return exported


def export_field_data(base_dir: str | Path, mesh, result: SimulationResult) -> list[Path]:
    output_dir = Path(base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []
    if mesh is None or not result.surface_intensity:
        return exported

    faces = np.hstack([np.full((len(mesh.faces), 1), 3), mesh.faces]).astype(np.int64).ravel()
    poly = pv.PolyData(mesh.vertices, faces)
    if len(result.surface_intensity) == poly.n_cells:
        poly.cell_data["surface_proxy"] = result.surface_intensity
    vtk_path = output_dir / "surface_proxy.vtp"
    poly.save(vtk_path)
    exported.append(vtk_path)
    return exported


def export_report_bundle(
    base_dir: str | Path,
    project: ProjectModel,
    result: SimulationResult,
    *,
    mesh=None,
    geometry_info: GeometryInfo | None = None,
    mesh_plan: MeshPlan | None = None,
    preflight_report: PreflightReport | None = None,
) -> list[Path]:
    output_dir = Path(base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = export_numeric_results(output_dir, result)
    exported.extend(export_field_data(output_dir, mesh, result))

    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "project": project.to_dict(),
                "result": {
                    "synthetic": result.synthetic,
                    "run_directory": result.run_directory,
                    "messages": result.messages,
                    "frequency_points": len(result.frequencies_hz),
                },
                "geometry": asdict(geometry_info) if geometry_info else None,
                "mesh_plan": asdict(mesh_plan) if mesh_plan else None,
                "preflight": {
                    "confidence_label": preflight_report.confidence_label,
                    "backend_status": asdict(preflight_report.backend_status),
                    "issues": [asdict(item) for item in preflight_report.issues],
                    "warnings": [asdict(item) for item in preflight_report.warnings],
                    "infos": [asdict(item) for item in preflight_report.infos],
                }
                if preflight_report
                else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    exported.append(summary_path)

    report_path = output_dir / "summary.txt"
    lines = [f"Projekt: {project.project_name}", f"Szintetikus eredmény: {'igen' if result.synthetic else 'nem'}"]
    if result.run_directory:
        lines.append(f"Run directory: {result.run_directory}")
    if mesh_plan:
        lines.append(f"Becsült memória [GB]: {mesh_plan.estimated_memory_gb:.2f}")
        lines.append(f"Becsült futásidő [perc]: {mesh_plan.estimated_runtime_minutes:.1f}")
        lines.append(f"Cellák hullámhosszonként: {mesh_plan.cells_per_wavelength}")
    if preflight_report:
        lines.append(f"Confidence: {preflight_report.confidence_label}")
        lines.extend(f"HIBA: {item.summary}" for item in preflight_report.issues)
        lines.extend(f"FIGYELMEZTETÉS: {item.summary}" for item in preflight_report.warnings)
        lines.extend(f"INFO: {item.summary}" for item in preflight_report.infos)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    exported.append(report_path)
    return exported
