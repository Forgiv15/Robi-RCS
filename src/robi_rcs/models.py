from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


SPEED_OF_LIGHT = 299_792_458.0
VACUUM_IMPEDANCE = 376.730313668


@dataclass(slots=True)
class GeometrySettings:
    file_path: str = ""
    unit: str = "mm"
    scale: float = 1.0
    rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    auto_repair: bool = True


@dataclass(slots=True)
class MaterialSettings:
    preset: str = "PEC"
    epsilon_r: float = 1.0
    mu_r: float = 1.0
    conductivity_s_per_m: float = 5.8e7
    loss_tangent: float = 0.0
    anisotropy: tuple[float, float, float] = (1.0, 1.0, 1.0)
    custom_presets: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass(slots=True)
class FrequencySettings:
    start_hz: float = 1.0e9
    stop_hz: float = 10.0e9
    samples: int = 101
    sweep_type: str = "linear"
    reference_hz: float = 5.0e9


@dataclass(slots=True)
class ExcitationSettings:
    simulation_mode: str = "monostatic"
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    observation_azimuth_deg: float = 180.0
    observation_elevation_deg: float = 0.0
    polarization: str = "linear_z"
    amplitude_v_per_m: float = 1.0
    excitation_type: str = "gaussian"
    plane_wave_box_factor: float = 0.8


@dataclass(slots=True)
class MeshSettings:
    auto_mesh: bool = True
    detail_preset: str = "normal"
    cells_per_wavelength: int = 20
    min_cell_size_m: float = 1.0e-3
    max_growth_ratio: float = 1.3
    pml_cells: int = 8
    cfl_factor: float = 0.9
    max_memory_gb: float = 12.0
    target_runtime_minutes: float = 30.0
    detail_level: int = 3


@dataclass(slots=True)
class ExportSettings:
    output_dir: str = "exports"
    chart_formats: list[str] = field(default_factory=lambda: ["png", "csv"])
    numeric_formats: list[str] = field(default_factory=lambda: ["csv", "json", "hdf5"])
    field_formats: list[str] = field(default_factory=lambda: ["vtk", "hdf5"])
    animation_formats: list[str] = field(default_factory=lambda: ["gif"])
    animation_fps: int = 20
    animation_frames: int = 48


@dataclass(slots=True)
class SolverSettings:
    openems_python_command: str = ""
    working_directory: str = "runs"
    num_threads: int = 0
    end_criteria: float = 1.0e-5
    max_timesteps: int = 100_000
    setup_only: bool = False


@dataclass(slots=True)
class HardwareProfile:
    cpu_name: str = "Intel Core i7 11th Gen"
    gpu_name: str = "RTX 3050 Ti"
    ram_gb: float = 16.0
    cell_updates_per_minute: float = 2.4e9


@dataclass(slots=True)
class ValidationMessage:
    severity: str
    summary: str
    details: str = ""


@dataclass(slots=True)
class BackendStatus:
    available: bool = False
    executable: str = ""
    version: str = ""
    details: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DependencyStatus:
    name: str
    available: bool
    details: str = ""


@dataclass(slots=True)
class RuntimeStatus:
    summary: str = ""
    overall_ready: bool = False
    ui_ready: bool = False
    openems_ready: bool = False
    python_executable: str = ""
    openems_root: str = ""
    backend_status: BackendStatus = field(default_factory=BackendStatus)
    dependencies: list[DependencyStatus] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PreflightReport:
    issues: list[ValidationMessage] = field(default_factory=list)
    warnings: list[ValidationMessage] = field(default_factory=list)
    infos: list[ValidationMessage] = field(default_factory=list)
    backend_status: BackendStatus = field(default_factory=BackendStatus)
    confidence_label: str = "Unknown"


@dataclass(slots=True)
class ProjectModel:
    project_name: str = "Untitled Project"
    description: str = ""
    geometry: GeometrySettings = field(default_factory=GeometrySettings)
    material: MaterialSettings = field(default_factory=MaterialSettings)
    frequency: FrequencySettings = field(default_factory=FrequencySettings)
    excitation: ExcitationSettings = field(default_factory=ExcitationSettings)
    mesh: MeshSettings = field(default_factory=MeshSettings)
    export: ExportSettings = field(default_factory=ExportSettings)
    solver: SolverSettings = field(default_factory=SolverSettings)
    hardware: HardwareProfile = field(default_factory=HardwareProfile)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectModel":
        return cls(
            project_name=data.get("project_name", "Untitled Project"),
            description=data.get("description", ""),
            geometry=GeometrySettings(**data.get("geometry", {})),
            material=MaterialSettings(**data.get("material", {})),
            frequency=FrequencySettings(**data.get("frequency", {})),
            excitation=ExcitationSettings(**data.get("excitation", {})),
            mesh=MeshSettings(**data.get("mesh", {})),
            export=ExportSettings(**data.get("export", {})),
            solver=SolverSettings(**data.get("solver", {})),
            hardware=HardwareProfile(**data.get("hardware", {})),
        )


@dataclass(slots=True)
class GeometryInfo:
    bounds_min_m: tuple[float, float, float]
    bounds_max_m: tuple[float, float, float]
    extents_m: tuple[float, float, float]
    center_m: tuple[float, float, float]
    triangle_count: int
    vertex_count: int
    watertight: bool
    surface_area_m2: float
    volume_m3: float | None
    min_feature_size_m: float
    file_format: str


@dataclass(slots=True)
class MeshPlan:
    lambda_min_m: float
    base_cell_size_m: float
    domain_padding_m: tuple[float, float, float]
    domain_size_m: tuple[float, float, float]
    cells_xyz: tuple[int, int, int]
    total_cells: int
    estimated_memory_gb: float
    estimated_runtime_minutes: float
    estimated_timestep_s: float
    estimated_timesteps: int
    cells_per_wavelength: int = 0
    mesh_adequacy_index: float = 0.0
    domain_adequacy_index: float = 0.0
    pml_adequacy_index: float = 0.0
    frequency_resolution_index: float = 0.0
    warnings: list[str] = field(default_factory=list)
    quality_label: str = "Good"


@dataclass(slots=True)
class SimulationResult:
    frequencies_hz: list[float]
    rcs_m2: list[float]
    copol_m2: list[float]
    crosspol_m2: list[float]
    angular_rcs_m2: list[float]
    angular_phi_deg: list[float]
    surface_intensity: list[float]
    field_frames_2d: list[list[float]]
    field_frames_shape_2d: tuple[int, int]
    field_frames_3d: list[list[float]]
    field_frames_shape_3d: tuple[int, int, int]
    synthetic: bool
    run_directory: str = ""
    messages: list[str] = field(default_factory=list)


def unit_scale_to_meter(unit: str) -> float:
    mapping = {
        "mm": 1e-3,
        "cm": 1e-2,
        "m": 1.0,
    }
    return mapping.get(unit, 1.0)


def ensure_project_extension(path: str | Path) -> Path:
    project_path = Path(path)
    if project_path.suffix.lower() != ".rcsproj":
        return project_path.with_suffix(".rcsproj")
    return project_path
