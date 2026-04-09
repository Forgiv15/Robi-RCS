from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict
from pathlib import Path
import sys

import gmsh
import numpy as np
import trimesh

from robi_rcs.models import (
    GeometryInfo,
    MeshPlan,
    ProjectModel,
    SimulationResult,
    SPEED_OF_LIGHT,
    VACUUM_IMPEDANCE,
    unit_scale_to_meter,
)


DETAIL_TO_CPW = {
    "coarse": 12,
    "normal": 18,
    "fine": 24,
    "expert": 30,
}


class SimulationCancelledError(RuntimeError):
    pass

OPENEMS_TEMPLATE = """from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import Z0
from openEMS.ports import UI_data


def unit_vector_from_angles(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    az = np.deg2rad(azimuth_deg)
    el = np.deg2rad(elevation_deg)
    return np.array([
        np.cos(el) * np.cos(az),
        np.cos(el) * np.sin(az),
        np.sin(el),
    ])


def build_polarization(pol: str) -> np.ndarray:
    if pol == "linear_x":
        return np.array([1.0, 0.0, 0.0])
    if pol == "linear_y":
        return np.array([0.0, 1.0, 0.0])
    return np.array([0.0, 0.0, 1.0])


job_path = Path(__file__).with_name("job.json")
job = json.loads(job_path.read_text(encoding="utf-8"))
project = job["project"]
mesh_plan = job["mesh_plan"]
geometry = job["geometry"]

work_path = job_path.parent
sim_path = work_path / 'simulation'

FDTD = openEMS(EndCriteria=project["solver"]["end_criteria"], NrTS=int(project["solver"]["max_timesteps"]))

if project["excitation"]["excitation_type"] == "harmonic":
    FDTD.SetSinusExcite(project["frequency"]["reference_hz"])
else:
    f0 = 0.5 * (project["frequency"]["start_hz"] + project["frequency"]["stop_hz"])
    fc = 0.5 * (project["frequency"]["stop_hz"] - project["frequency"]["start_hz"])
    FDTD.SetGaussExcite(f0, fc)

FDTD.SetBoundaryCond([f'PML_{project["mesh"]["pml_cells"]}'] * 6)
FDTD.SetTimeStepFactor(project["mesh"]["cfl_factor"])

CSX = ContinuousStructure()
FDTD.SetCSX(CSX)
grid = CSX.GetGrid()
grid.SetDeltaUnit(1.0)

grid.SetLines('x', mesh_plan["mesh_lines_x_m"])
grid.SetLines('y', mesh_plan["mesh_lines_y_m"])
grid.SetLines('z', mesh_plan["mesh_lines_z_m"])
grid.SmoothMeshLines('all', mesh_plan["base_cell_size_m"], ratio=project["mesh"]["max_growth_ratio"])

material = project["material"]
if material["preset"] == "PEC":
    target = CSX.AddMetal('target')
else:
    target = CSX.AddMaterial(
        'target',
        epsilon=material["epsilon_r"],
        mue=material["mu_r"],
        kappa=material["conductivity_s_per_m"],
    )

target.AddPolyhedronReader(job["openems_geometry_file"], priority=10)
FDTD.AddEdges2Grid('all', properties=target)

k_dir = unit_vector_from_angles(project["excitation"]["azimuth_deg"], project["excitation"]["elevation_deg"])
e_dir = build_polarization(project["excitation"]["polarization"])

pw_exc = CSX.AddExcitation('plane_wave', exc_type=10, exc_val=e_dir)
pw_exc.SetPropagationDir(k_dir)
pw_exc.SetFrequency(project["frequency"]["reference_hz"])

sim_box = np.array(mesh_plan["domain_size_m"])
pw_box = sim_box * project["excitation"]["plane_wave_box_factor"] * 0.5
pw_exc.AddBox(-pw_box, pw_box)

nf2ff = FDTD.CreateNF2FFBox()
FDTD.Run(str(sim_path), cleanup=True, verbose=1, numThreads=int(project["solver"]["num_threads"]))

if project["frequency"]["samples"] > 1:
    if project["frequency"]["sweep_type"] == "logarithmic":
        freq = np.geomspace(project["frequency"]["start_hz"], project["frequency"]["stop_hz"], project["frequency"]["samples"])
    else:
        freq = np.linspace(project["frequency"]["start_hz"], project["frequency"]["stop_hz"], project["frequency"]["samples"])
else:
    freq = np.array([project["frequency"]["reference_hz"]])

ef = UI_data('et', str(sim_path), freq)
pin = 0.5 * np.linalg.norm(e_dir) ** 2 / Z0 * np.abs(np.array(ef.ui_f_val[0])) ** 2

theta = np.array([90.0 - project["excitation"]["observation_elevation_deg"]])
phi = np.array([project["excitation"]["observation_azimuth_deg"]])
nf2ff_res = nf2ff.CalcNF2FF(str(sim_path), freq, theta, phi, outfile='nf2ff.h5', verbose=0)

p_rad = np.array([nf2ff_res.P_rad[idx][0][0] for idx in range(len(freq))])
rcs = 4.0 * np.pi * p_rad / pin

e_theta = np.array([complex(nf2ff_res.E_theta[idx][0][0]) for idx in range(len(freq))])
e_phi = np.array([complex(nf2ff_res.E_phi[idx][0][0]) for idx in range(len(freq))])

if project["excitation"]["polarization"] in {"rhcp", "lhcp"}:
    e_co = np.array([complex(nf2ff_res.E_cprh[idx][0][0]) for idx in range(len(freq))])
    e_cross = np.array([complex(nf2ff_res.E_cplh[idx][0][0]) for idx in range(len(freq))])
else:
    e_co = e_theta
    e_cross = e_phi

copol = 4.0 * np.pi * np.abs(e_co) ** 2 / (np.abs(np.array(ef.ui_f_val[0])) ** 2)
crosspol = 4.0 * np.pi * np.abs(e_cross) ** 2 / (np.abs(np.array(ef.ui_f_val[0])) ** 2)

phi_sweep = np.linspace(-180.0, 180.0, 181)
pattern = nf2ff.CalcNF2FF(str(sim_path), np.array([project["frequency"]["reference_hz"]]), np.array([90.0]), phi_sweep, outfile='pattern.h5', verbose=0)
pin_ref = pin[0] if len(pin) else 1.0
angular_rcs = [float(4.0 * np.pi * pattern.P_rad[0][0][idx] / pin_ref) for idx in range(len(phi_sweep))]

result = {
    'frequencies_hz': freq.tolist(),
    'rcs_m2': rcs.real.tolist(),
    'copol_m2': copol.real.tolist(),
    'crosspol_m2': crosspol.real.tolist(),
    'angular_phi_deg': phi_sweep.tolist(),
    'angular_rcs_m2': angular_rcs,
    'synthetic': False,
    'run_directory': str(work_path),
    'messages': ['openEMS run completed'],
}

Path(work_path / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
"""


def has_openems_backend(python_command: str | None = None) -> bool:
    if python_command:
        cmd = [python_command, "-c", "import openEMS, CSXCAD"]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return True
        except Exception:
            return False
    return False


def load_geometry(project: ProjectModel) -> tuple[trimesh.Trimesh, GeometryInfo]:
    geometry_path = Path(project.geometry.file_path)
    if not geometry_path.exists():
        raise FileNotFoundError(f"Geometry file not found: {geometry_path}")

    source_path = geometry_path
    temp_dir: Path | None = None
    if geometry_path.suffix.lower() in {".step", ".stp"}:
        temp_dir = Path(tempfile.mkdtemp(prefix="robi_rcs_step_"))
        source_path = _convert_step_to_stl(geometry_path, temp_dir)

    try:
        loaded = trimesh.load_mesh(source_path, process=project.geometry.auto_repair)
        mesh = _scene_to_mesh(loaded)
        scale_to_meter = unit_scale_to_meter(project.geometry.unit) * project.geometry.scale
        mesh.apply_scale(scale_to_meter)

        rotation = np.deg2rad(project.geometry.rotation_deg)
        matrix = trimesh.transformations.euler_matrix(rotation[0], rotation[1], rotation[2], axes="sxyz")
        mesh.apply_transform(matrix)
        mesh.apply_translation(np.array(project.geometry.position_m))

        edge_lengths = np.asarray(mesh.edges_unique_length) if mesh.edges_unique is not None else np.array([])
        min_feature = float(np.percentile(edge_lengths, 10)) if edge_lengths.size else float(min(mesh.extents) / 10.0)

        bounds = mesh.bounds
        info = GeometryInfo(
            bounds_min_m=tuple(float(x) for x in bounds[0]),
            bounds_max_m=tuple(float(x) for x in bounds[1]),
            extents_m=tuple(float(x) for x in mesh.extents),
            center_m=tuple(float(x) for x in mesh.bounding_box.centroid),
            triangle_count=int(len(mesh.faces)),
            vertex_count=int(len(mesh.vertices)),
            watertight=bool(mesh.is_watertight),
            surface_area_m2=float(mesh.area),
            volume_m3=float(mesh.volume) if mesh.is_volume else None,
            min_feature_size_m=max(min_feature, 1e-6),
            file_format=geometry_path.suffix.lower().lstrip("."),
        )
        return mesh, info
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)


def create_mesh_plan(project: ProjectModel, geometry_info: GeometryInfo) -> MeshPlan:
    cpw = DETAIL_TO_CPW.get(project.mesh.detail_preset, project.mesh.cells_per_wavelength) + (project.mesh.detail_level - 3) * 2
    cpw = max(cpw, 10)

    best_plan = _build_mesh_plan(project, geometry_info, cpw)
    while project.mesh.auto_mesh and best_plan.estimated_runtime_minutes > project.mesh.target_runtime_minutes and cpw > 10:
        cpw -= 1
        best_plan = _build_mesh_plan(project, geometry_info, cpw)

    warnings = list(best_plan.warnings)
    if cpw < 15:
        warnings.append("A cél futásidő miatt a cella/hullámhossz érték 15 alá csökkent; az eredmény pontossága korlátozott lehet.")
    if best_plan.estimated_memory_gb > project.mesh.max_memory_gb:
        warnings.append("A becsült memóriaigény meghaladja a beállított korlátot.")
    if not geometry_info.watertight:
        warnings.append("A geometria nem watertight; a szórási eredmények torzulhatnak.")
    best_plan.warnings = warnings
    if any("meghaladja" in item.lower() or "korlátozott" in item.lower() for item in warnings):
        best_plan.quality_label = "Warning"
    if best_plan.estimated_memory_gb > project.hardware.ram_gb:
        best_plan.quality_label = "Critical"
    return best_plan


def prepare_openems_job(
    project: ProjectModel,
    mesh: trimesh.Trimesh,
    geometry_info: GeometryInfo,
    mesh_plan: MeshPlan,
) -> Path:
    base_run_dir = Path(project.solver.working_directory or "runs").resolve()
    base_run_dir.mkdir(parents=True, exist_ok=True)
    run_dir = base_run_dir / _safe_slug(project.project_name)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_dir = run_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    openems_geometry_file = _export_openems_geometry(mesh, Path(project.geometry.file_path), run_dir)
    mesh_lines = _mesh_lines_from_plan(geometry_info, mesh_plan)

    job = {
        "project": asdict(project),
        "geometry": asdict(geometry_info),
        "mesh_plan": {
            **asdict(mesh_plan),
            **mesh_lines,
        },
        "openems_geometry_file": str(openems_geometry_file),
        "run_directory": str(run_dir),
    }
    (run_dir / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    (run_dir / "run_openems_job.py").write_text(OPENEMS_TEMPLATE, encoding="utf-8")
    return run_dir


def run_openems_job(
    project: ProjectModel,
    run_dir: Path,
    python_command: str | None = None,
    cancel_event: threading.Event | None = None,
    process_callback=None,
) -> SimulationResult:
    python_command = (python_command or project.solver.openems_python_command).strip()
    if not python_command:
        python_command = sys.executable

    cmd = [python_command, str(run_dir / "run_openems_job.py")]
    timeout_seconds = max(int(project.mesh.target_runtime_minutes * 60 * 3), 300)
    deadline = time.monotonic() + timeout_seconds
    process = subprocess.Popen(cmd, cwd=run_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if process_callback is not None:
        process_callback(process)

    try:
        while process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                _terminate_process(process)
                raise SimulationCancelledError("A szimulacio felhasznaloi keresre megszakadt.")
            if time.monotonic() > deadline:
                _terminate_process(process)
                raise RuntimeError("Az openEMS futas idotullepes miatt leallt.")
            time.sleep(0.1)

        stdout, stderr = process.communicate()
    finally:
        if process_callback is not None:
            process_callback(None)

    if process.returncode != 0:
        stderr = stderr.strip() or stdout.strip()
        raise RuntimeError(stderr or "Az openEMS futás sikertelen volt.")

    result_path = run_dir / "result.json"
    if not result_path.exists():
        raise RuntimeError("Az openEMS futás nem hozott létre result.json fájlt.")

    data = json.loads(result_path.read_text(encoding="utf-8"))
    result = _result_from_dict(data, synthetic=False)
    result.run_directory = str(run_dir)
    return result


def _terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
            process.wait(timeout=5)
        except Exception:
            pass


def create_synthetic_result(mesh: trimesh.Trimesh, geometry_info: GeometryInfo, project: ProjectModel) -> SimulationResult:
    freq = _frequency_array(project)
    ref_radius = max(geometry_info.extents_m) * 0.5
    cross_section = math.pi * ref_radius * ref_radius
    wavelength = SPEED_OF_LIGHT / np.maximum(freq, 1.0)
    electrical_size = 2.0 * math.pi * ref_radius / wavelength

    detail_factor = 0.8 + 0.1 * project.mesh.detail_level
    rcs = cross_section * (0.35 + 0.55 * np.sin(electrical_size * detail_factor) ** 2 + 0.25 * electrical_size)
    copol = rcs * 0.85
    crosspol = rcs * 0.15 * (0.4 + 0.6 * np.cos(np.linspace(0.0, math.pi, len(freq))) ** 2)

    phi = np.linspace(-180.0, 180.0, 181)
    az = math.radians(project.excitation.azimuth_deg)
    angular = cross_section * (0.2 + np.cos(np.deg2rad(phi) - az) ** 2)

    incident_dir = np.array([
        math.cos(math.radians(project.excitation.elevation_deg)) * math.cos(math.radians(project.excitation.azimuth_deg)),
        math.cos(math.radians(project.excitation.elevation_deg)) * math.sin(math.radians(project.excitation.azimuth_deg)),
        math.sin(math.radians(project.excitation.elevation_deg)),
    ])
    face_normals = mesh.face_normals if len(mesh.face_normals) else np.zeros((0, 3))
    surface_intensity = np.clip(face_normals @ (-incident_dir), 0.0, 1.0)
    if surface_intensity.size == 0:
        surface_intensity = np.zeros(len(mesh.faces))

    field_frames_2d, shape_2d = _create_2d_frames(project)
    field_frames_3d, shape_3d = _create_3d_frames(project)

    return SimulationResult(
        frequencies_hz=freq.tolist(),
        rcs_m2=rcs.tolist(),
        copol_m2=copol.tolist(),
        crosspol_m2=crosspol.tolist(),
        angular_rcs_m2=angular.tolist(),
        angular_phi_deg=phi.tolist(),
        surface_intensity=surface_intensity.tolist(),
        field_frames_2d=field_frames_2d,
        field_frames_shape_2d=shape_2d,
        field_frames_3d=field_frames_3d,
        field_frames_shape_3d=shape_3d,
        synthetic=True,
        run_directory="",
        messages=[
            "openEMS backend nem volt elérhető; szintetikus demonstrációs eredmény készült.",
            "Valódi solver futtatáshoz adj meg openEMS-et tartalmazó python környezetet.",
        ],
    )


def _build_mesh_plan(project: ProjectModel, geometry_info: GeometryInfo, cells_per_wavelength: int) -> MeshPlan:
    epsilon = max(project.material.epsilon_r, 1.0)
    mu = max(project.material.mu_r, 1.0)
    lambda_min = SPEED_OF_LIGHT / (project.frequency.stop_hz * math.sqrt(epsilon * mu))

    feature_driven = max(geometry_info.min_feature_size_m / 4.0, 1.0e-6)
    wave_driven = lambda_min / cells_per_wavelength
    base_cell = max(project.mesh.min_cell_size_m, min(feature_driven, wave_driven))

    padding_lambda = 0.75 if project.excitation.simulation_mode == "bistatic" else 0.5
    padding = tuple(max(padding_lambda * lambda_min, extent * 0.15) for extent in geometry_info.extents_m)
    pml_pad = 2.0 * project.mesh.pml_cells * base_cell
    domain_size = tuple(float(extent + 2.0 * pad + pml_pad) for extent, pad in zip(geometry_info.extents_m, padding))
    cells_xyz = tuple(max(int(math.ceil(size / base_cell)), 8) for size in domain_size)
    total_cells = int(cells_xyz[0] * cells_xyz[1] * cells_xyz[2])

    timestep = project.mesh.cfl_factor * base_cell / (SPEED_OF_LIGHT * math.sqrt(3.0))
    domain_diag = float(math.sqrt(sum(size * size for size in domain_size)))
    timesteps = int(math.ceil((14.0 * domain_diag / SPEED_OF_LIGHT) / max(timestep, 1e-15)))
    sweep_factor = 1.0 + math.log10(max(project.frequency.samples, 2)) * 0.2
    workload = total_cells * timesteps * sweep_factor
    runtime_minutes = workload / max(project.hardware.cell_updates_per_minute, 1.0)
    memory_gb = total_cells * 160.0 / (1024.0 ** 3)
    mesh_adequacy_index = min(cells_per_wavelength / (22.0 if epsilon * mu > 2.5 else 18.0), 1.0)
    domain_adequacy_index = min(min(padding) / max(0.5 * lambda_min, 1e-12), 1.0)
    pml_adequacy_index = min(project.mesh.pml_cells / 10.0, 1.0)
    frequency_resolution_index = min(project.frequency.samples / (121.0 if project.frequency.sweep_type == "linear" else 81.0), 1.0)

    warnings: list[str] = []
    if cells_per_wavelength < 15:
        warnings.append("A cella/hullámhossz arány alacsony a nagyfrekvenciás tartományban.")
    if memory_gb > project.mesh.max_memory_gb:
        warnings.append("A becsült memóriaigény meghaladja a beállított limitet.")
    if min(geometry_info.extents_m) < 3.0 * base_cell:
        warnings.append("A legkisebb geometriai részlet csak néhány cellával reprezentálható.")

    return MeshPlan(
        lambda_min_m=lambda_min,
        base_cell_size_m=base_cell,
        domain_padding_m=padding,
        domain_size_m=domain_size,
        cells_xyz=cells_xyz,
        total_cells=total_cells,
        estimated_memory_gb=memory_gb,
        estimated_runtime_minutes=runtime_minutes,
        estimated_timestep_s=timestep,
        estimated_timesteps=timesteps,
        cells_per_wavelength=cells_per_wavelength,
        mesh_adequacy_index=mesh_adequacy_index,
        domain_adequacy_index=domain_adequacy_index,
        pml_adequacy_index=pml_adequacy_index,
        frequency_resolution_index=frequency_resolution_index,
        warnings=warnings,
    )


def _scene_to_mesh(loaded: trimesh.Trimesh | trimesh.Scene) -> trimesh.Trimesh:
    if isinstance(loaded, trimesh.Scene):
        meshes = [geometry for geometry in loaded.geometry.values() if isinstance(geometry, trimesh.Trimesh)]
        if not meshes:
            raise ValueError("A fájl nem tartalmazott feldolgozható mesh geometriát.")
        return trimesh.util.concatenate(meshes)
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError("A fájlból nem sikerült háromszögelhető mesh geometriát létrehozni.")
    return loaded


def _convert_step_to_stl(step_path: Path, temp_dir: Path) -> Path:
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.open(str(step_path))
        gmsh.model.mesh.generate(2)
        target = temp_dir / f"{step_path.stem}.stl"
        gmsh.write(str(target))
        return target
    finally:
        gmsh.finalize()


def _export_openems_geometry(mesh: trimesh.Trimesh, original_path: Path, run_dir: Path) -> Path:
    suffix = original_path.suffix.lower()
    target = run_dir / f"geometry{'.ply' if suffix == '.ply' else '.stl'}"
    export_mesh = mesh.copy()
    if suffix == ".ply":
        export_mesh.export(target)
        return target
    export_mesh.export(target)
    return target


def _mesh_lines_from_plan(geometry_info: GeometryInfo, mesh_plan: MeshPlan) -> dict[str, list[float]]:
    mins = np.array(geometry_info.center_m) - np.array(mesh_plan.domain_size_m) / 2.0
    x = np.linspace(mins[0], mins[0] + mesh_plan.domain_size_m[0], mesh_plan.cells_xyz[0] + 1)
    y = np.linspace(mins[1], mins[1] + mesh_plan.domain_size_m[1], mesh_plan.cells_xyz[1] + 1)
    z = np.linspace(mins[2], mins[2] + mesh_plan.domain_size_m[2], mesh_plan.cells_xyz[2] + 1)
    return {
        "mesh_lines_x_m": x.tolist(),
        "mesh_lines_y_m": y.tolist(),
        "mesh_lines_z_m": z.tolist(),
    }


def _frequency_array(project: ProjectModel) -> np.ndarray:
    if project.frequency.sweep_type == "logarithmic":
        return np.geomspace(project.frequency.start_hz, project.frequency.stop_hz, project.frequency.samples)
    return np.linspace(project.frequency.start_hz, project.frequency.stop_hz, project.frequency.samples)


def _create_2d_frames(project: ProjectModel) -> tuple[list[list[float]], tuple[int, int]]:
    size = 96
    frames: list[list[float]] = []
    x = np.linspace(-1.0, 1.0, size)
    xx, yy = np.meshgrid(x, x)
    for idx in range(project.export.animation_frames):
        phase = 2.0 * math.pi * idx / max(project.export.animation_frames, 1)
        frame = np.sin(7.0 * xx - phase) * np.exp(-2.2 * (yy ** 2)) + 0.6 * np.cos(4.0 * np.sqrt(xx ** 2 + yy ** 2) + phase)
        frames.append(frame.astype(float).ravel().tolist())
    return frames, (size, size)


def _create_3d_frames(project: ProjectModel) -> tuple[list[list[float]], tuple[int, int, int]]:
    size = 24
    coords = np.linspace(-1.0, 1.0, size)
    xx, yy, zz = np.meshgrid(coords, coords, coords, indexing="ij")
    frames: list[list[float]] = []
    radius = np.sqrt(xx ** 2 + yy ** 2 + zz ** 2)
    for idx in range(project.export.animation_frames):
        phase = 2.0 * math.pi * idx / max(project.export.animation_frames, 1)
        field = np.sin(8.0 * radius - phase) * np.exp(-2.0 * radius) + 0.35 * np.cos(5.0 * xx + phase)
        frames.append(field.astype(float).ravel().tolist())
    return frames, (size, size, size)


def _result_from_dict(data: dict[str, object], synthetic: bool) -> SimulationResult:
    return SimulationResult(
        frequencies_hz=list(data.get("frequencies_hz", [])),
        rcs_m2=list(data.get("rcs_m2", [])),
        copol_m2=list(data.get("copol_m2", [])),
        crosspol_m2=list(data.get("crosspol_m2", [])),
        angular_rcs_m2=list(data.get("angular_rcs_m2", [])),
        angular_phi_deg=list(data.get("angular_phi_deg", [])),
        surface_intensity=list(data.get("surface_intensity", [])),
        field_frames_2d=list(data.get("field_frames_2d", [])),
        field_frames_shape_2d=tuple(data.get("field_frames_shape_2d", (0, 0))),
        field_frames_3d=list(data.get("field_frames_3d", [])),
        field_frames_shape_3d=tuple(data.get("field_frames_shape_3d", (0, 0, 0))),
        synthetic=bool(data.get("synthetic", synthetic)),
        run_directory=str(data.get("run_directory", "")),
        messages=list(data.get("messages", [])),
    )


def _safe_slug(text: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in text).strip("_")
    return slug or "project"
