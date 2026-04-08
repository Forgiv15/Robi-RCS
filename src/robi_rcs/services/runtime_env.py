from __future__ import annotations

import os
import sys
from pathlib import Path


def detect_openems_root() -> Path | None:
    candidates: list[Path] = []

    env_value = os.environ.get("OPENEMS_INSTALL_PATH", "").strip()
    if env_value:
        candidates.append(Path(env_value))

    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root / "openEMS")
    candidates.append(Path.cwd() / "openEMS")

    executable = Path(sys.executable).resolve()
    for parent in executable.parents:
        candidates.append(parent / "openEMS")

    for candidate in candidates:
        if candidate.exists() and (candidate / "openEMS.exe").exists() and (candidate / "python").exists():
            return candidate
    return None


def prepare_openems_runtime() -> Path | None:
    root = detect_openems_root()
    if root is None:
        return None

    root_str = str(root)
    os.environ["OPENEMS_INSTALL_PATH"] = root_str
    path_parts = os.environ.get("PATH", "").split(os.pathsep) if os.environ.get("PATH") else []
    if root_str not in path_parts:
        os.environ["PATH"] = root_str + os.pathsep + os.environ.get("PATH", "")

    if os.name == "nt":
        try:
            os.add_dll_directory(root_str)
        except (AttributeError, FileNotFoundError, OSError):
            pass
    return root