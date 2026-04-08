from __future__ import annotations

import json
import subprocess
import sys

from robi_rcs.models import BackendStatus, GeometryInfo, MeshPlan, PreflightReport, ProjectModel, ValidationMessage
from robi_rcs.services.runtime_env import prepare_openems_runtime


BACKEND_INSPECTION_SNIPPET = """
import importlib.metadata
import importlib.util
import json

origins = {}
for name in ("openEMS", "CSXCAD"):
    spec = importlib.util.find_spec(name)
    origins[name] = spec.origin if spec else ""

version = ""
for package_name in ("openEMS", "openems", "CSXCAD"):
    try:
        version = importlib.metadata.version(package_name)
        break
    except Exception:
        pass

print(json.dumps({
    "openems": bool(origins["openEMS"]),
    "csxcad": bool(origins["CSXCAD"]),
    "version": version,
    "origins": origins,
}))
""".strip()


def inspect_openems_backend(python_command: str) -> BackendStatus:
    prepare_openems_runtime()
    command = python_command.strip() if python_command else ""
    if not command:
        command = sys.executable

    try:
        process = subprocess.run(
            [command, "-c", BACKEND_INSPECTION_SNIPPET],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except OSError as exc:
        return BackendStatus(available=False, executable=command, details=[str(exc)])
    except Exception as exc:
        return BackendStatus(available=False, executable=command, details=[f"Backend ellenőrzés hiba: {exc}"])

    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or "Ismeretlen hiba a backend ellenőrzésekor."
        return BackendStatus(available=False, executable=command, details=[detail])

    try:
        payload = json.loads(process.stdout.strip().splitlines()[-1])
    except Exception:
        return BackendStatus(
            available=False,
            executable=command,
            details=["Az openEMS környezet ellenőrzésének kimenete nem volt értelmezhető."],
        )

    available = bool(payload.get("openems")) and bool(payload.get("csxcad"))
    details = []
    if payload.get("origins", {}).get("openEMS"):
        details.append(f"openEMS modul: {payload['origins']['openEMS']}")
    if payload.get("origins", {}).get("CSXCAD"):
        details.append(f"CSXCAD modul: {payload['origins']['CSXCAD']}")
    if not available:
        details.append("A megadott Python környezetből az openEMS és CSXCAD nem importálható együtt.")
    return BackendStatus(
        available=available,
        executable=command,
        version=str(payload.get("version", "")),
        details=details,
    )


def build_preflight_report(
    project: ProjectModel,
    geometry_info: GeometryInfo,
    mesh_plan: MeshPlan,
    backend_status: BackendStatus,
) -> PreflightReport:
    report = PreflightReport(backend_status=backend_status)

    def add_issue(summary: str, details: str = "") -> None:
        report.issues.append(ValidationMessage("ERROR", summary, details))

    def add_warning(summary: str, details: str = "") -> None:
        report.warnings.append(ValidationMessage("WARNING", summary, details))

    def add_info(summary: str, details: str = "") -> None:
        report.infos.append(ValidationMessage("INFO", summary, details))

    if project.frequency.start_hz <= 0.0:
        add_issue("A kezdő frekvencia csak pozitív lehet.")
    if project.frequency.stop_hz <= project.frequency.start_hz:
        add_issue("A végfrekvenciának nagyobbnak kell lennie a kezdő frekvenciánál.")
    if project.frequency.samples < 1:
        add_issue("Legalább egy frekvenciamintára szükség van.")
    if project.excitation.amplitude_v_per_m <= 0.0:
        add_issue("A gerjesztés amplitúdójának pozitívnak kell lennie.")
    if geometry_info.triangle_count <= 0:
        add_issue("A betöltött geometriából nem maradt felhasználható háromszög.")
    if mesh_plan.estimated_memory_gb > project.hardware.ram_gb * 1.35:
        add_issue(
            "A becsült memóriaigény túl magas ehhez a hardverprofilhoz.",
            f"Becslés: {mesh_plan.estimated_memory_gb:.2f} GB, elérhető RAM: {project.hardware.ram_gb:.2f} GB.",
        )

    if not geometry_info.watertight:
        add_warning("A geometria nem watertight.", "Nyitott felületnél a szórási eredmények fizikailag bizonytalanabbak lehetnek.")
    if mesh_plan.mesh_adequacy_index < 0.8:
        add_warning("A mesh-felbontás a magasabb frekvenciákon határeset lehet.")
    if mesh_plan.domain_adequacy_index < 0.8:
        add_warning("A számítási domén paddingja kicsi lehet a megbízható NF2FF eredményhez.")
    if mesh_plan.pml_adequacy_index < 0.8:
        add_warning("A PML vastagsága konzervatívabb beállítást igényelhet széles sávra vagy sekély beesésre.")
    if mesh_plan.frequency_resolution_index < 0.6:
        add_warning("A frekvenciaminták száma korlátozhatja a rezonanciák felbontását.")
    if mesh_plan.estimated_runtime_minutes > project.mesh.target_runtime_minutes * 1.15:
        add_warning(
            "A becsült futásidő meghaladja a kívánt célt.",
            f"Cél: {project.mesh.target_runtime_minutes:.1f} perc, becslés: {mesh_plan.estimated_runtime_minutes:.1f} perc.",
        )
    for warning in mesh_plan.warnings:
        add_warning(warning)

    if backend_status.available:
        add_info(
            "Valós openEMS backend elérhető.",
            f"Python: {backend_status.executable}" + (f", verzió: {backend_status.version}" if backend_status.version else ""),
        )
    else:
        add_info("Valós openEMS backend nincs aktív állapotban.", "A futás szintetikus demonstrációs eredményre esik vissza, hacsak nem adsz meg működő python.exe utat.")

    add_info("Automatikus mesh terv elkészült.", f"Cellák hullámhosszonként: {mesh_plan.cells_per_wavelength}")
    add_info(
        "Erőforrásbecslés elkészült.",
        f"Memória: {mesh_plan.estimated_memory_gb:.2f} GB, futásidő: {mesh_plan.estimated_runtime_minutes:.1f} perc, cellák: {mesh_plan.total_cells:,}",
    )

    score = (
        mesh_plan.mesh_adequacy_index
        + mesh_plan.domain_adequacy_index
        + mesh_plan.pml_adequacy_index
        + mesh_plan.frequency_resolution_index
    ) / 4.0
    if report.issues:
        report.confidence_label = "Blocking issues"
    elif score >= 0.85 and not report.warnings:
        report.confidence_label = "Good"
    elif score >= 0.65:
        report.confidence_label = "Acceptable"
    else:
        report.confidence_label = "Low confidence"
    return report


def format_preflight_report(report: PreflightReport, mesh_plan: MeshPlan) -> str:
    lines = [f"Confidence: {report.confidence_label}", ""]
    lines.append("Backend:")
    if report.backend_status.executable:
        lines.append(f"- Python: {report.backend_status.executable}")
    lines.append(f"- openEMS elérhető: {'igen' if report.backend_status.available else 'nem'}")
    if report.backend_status.version:
        lines.append(f"- Verzió: {report.backend_status.version}")
    for detail in report.backend_status.details:
        lines.append(f"- {detail}")
    lines.append("")
    lines.append("Adequacy indexek:")
    lines.append(f"- Mesh: {mesh_plan.mesh_adequacy_index:.2f}")
    lines.append(f"- Domén: {mesh_plan.domain_adequacy_index:.2f}")
    lines.append(f"- PML: {mesh_plan.pml_adequacy_index:.2f}")
    lines.append(f"- Frekvenciafelbontás: {mesh_plan.frequency_resolution_index:.2f}")

    for title, messages in (("Hibák", report.issues), ("Figyelmeztetések", report.warnings), ("Információk", report.infos)):
        lines.append("")
        lines.append(f"{title}:")
        if not messages:
            lines.append("- nincs")
            continue
        for item in messages:
            lines.append(f"- {item.summary}")
            if item.details:
                lines.append(f"  {item.details}")
    return "\n".join(lines)