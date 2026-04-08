from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robi_rcs.services.backend import create_mesh_plan, create_synthetic_result, load_geometry
from robi_rcs.services.diagnostics import build_preflight_report, inspect_openems_backend
from robi_rcs.models import ProjectModel


class BackendWorkflowTest(unittest.TestCase):
    def test_synthetic_workflow_and_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            geometry_path = Path(temp_dir) / "sphere.stl"
            trimesh.creation.icosphere(subdivisions=2, radius=0.25).export(geometry_path)

            project = ProjectModel()
            project.geometry.file_path = str(geometry_path)
            project.geometry.unit = "m"
            project.frequency.start_hz = 2.0e9
            project.frequency.stop_hz = 12.0e9
            project.frequency.samples = 81

            mesh, geometry_info = load_geometry(project)
            mesh_plan = create_mesh_plan(project, geometry_info)
            backend_status = inspect_openems_backend("")
            preflight = build_preflight_report(project, geometry_info, mesh_plan, backend_status)
            result = create_synthetic_result(mesh, geometry_info, project)

            self.assertGreater(geometry_info.triangle_count, 0)
            self.assertGreater(mesh_plan.total_cells, 0)
            self.assertFalse(preflight.issues)
            self.assertGreater(len(result.frequencies_hz), 10)
            self.assertTrue(result.synthetic)


if __name__ == "__main__":
    unittest.main()