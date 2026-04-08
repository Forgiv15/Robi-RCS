from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robi_rcs.models import ProjectModel
from robi_rcs.services.backend import create_mesh_plan, create_synthetic_result, load_geometry
from robi_rcs.services.diagnostics import build_preflight_report, inspect_openems_backend
from robi_rcs.services.export_service import export_report_bundle


class ExportBundleTest(unittest.TestCase):
    def test_bundle_exports_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            geometry_path = Path(temp_dir) / "sphere.stl"
            export_dir = Path(temp_dir) / "exports"
            trimesh.creation.icosphere(subdivisions=2, radius=0.1).export(geometry_path)

            project = ProjectModel()
            project.geometry.file_path = str(geometry_path)
            project.geometry.unit = "m"

            mesh, geometry_info = load_geometry(project)
            mesh_plan = create_mesh_plan(project, geometry_info)
            result = create_synthetic_result(mesh, geometry_info, project)
            preflight = build_preflight_report(project, geometry_info, mesh_plan, inspect_openems_backend(""))

            exported = export_report_bundle(
                export_dir,
                project,
                result,
                mesh=mesh,
                geometry_info=geometry_info,
                mesh_plan=mesh_plan,
                preflight_report=preflight,
            )

            exported_names = {path.name for path in exported}
            self.assertIn("rcs_vs_frequency.csv", exported_names)
            self.assertIn("result.h5", exported_names)
            self.assertIn("summary.json", exported_names)
            self.assertIn("summary.txt", exported_names)
            self.assertIn("surface_proxy.vtp", exported_names)


if __name__ == "__main__":
    unittest.main()