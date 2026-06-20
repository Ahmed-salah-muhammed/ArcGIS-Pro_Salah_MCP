"""Self-healing ArcPy discovery.

ArcPy ships only with ArcGIS Pro and lives in its bundled conda environment
(``arcgispro-py3``). If the MCP server happens to be started with a *different*
Python interpreter (e.g. a generic venv or ``uvx``), ``import arcpy`` will fail.

This module locates ArcGIS Pro's interpreter and, when needed, re-executes the
current process under it so the Pro tools work no matter where the package was
installed. This mirrors the "self-healing install" idea from CLI-Anything.

Discovery order:
    1. CLI_ANYTHING_ARCGIS_PYTHON environment variable (explicit override)
    2. Common install paths on Windows
    3. The Windows registry key  SOFTWARE\\ESRI\\ArcGISPro -> InstallDir
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_COMMON_INSTALL_ROOTS = [
    r"C:\Program Files\ArcGIS\Pro",
    r"C:\Program Files (x86)\ArcGIS\Pro",
]

_REL_PY = r"bin\Python\envs\arcgispro-py3\python.exe"


def arcpy_available() -> bool:
    """Return True if ``arcpy`` can be imported in the current interpreter."""
    try:
        import arcpy  # noqa: F401
        return True
    except Exception:
        return False


def _from_registry() -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg  # type: ignore
    except Exception:
        return None
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, r"SOFTWARE\ESRI\ArcGISPro") as key:
                install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                candidate = Path(install_dir) / _REL_PY
                if candidate.exists():
                    return str(candidate)
        except OSError:
            continue
    return None


def find_arcgis_python() -> str | None:
    """Locate ArcGIS Pro's ``arcgispro-py3`` python.exe, or None if not found."""
    env = os.environ.get("CLI_ANYTHING_ARCGIS_PYTHON")
    if env and Path(env).exists():
        return env

    for root in _COMMON_INSTALL_ROOTS:
        candidate = Path(root) / _REL_PY
        if candidate.exists():
            return str(candidate)

    return _from_registry()


def ensure_arcpy() -> None:
    """Make sure ArcPy is importable.

    If it already is, return. Otherwise try to re-exec this process under
    ArcGIS Pro's interpreter. Raises RuntimeError if Pro cannot be found.
    """
    if arcpy_available():
        return

    target = find_arcgis_python()
    if not target:
        raise RuntimeError(
            "ArcPy is not available and ArcGIS Pro's Python could not be found. "
            "Install ArcGIS Pro, or set CLI_ANYTHING_ARCGIS_PYTHON to its "
            "arcgispro-py3 python.exe."
        )

    # Avoid infinite re-exec loops.
    if os.environ.get("_ARCGIS_SALAH_REEXEC") == "1":
        raise RuntimeError(
            f"Re-executed under {target} but ArcPy still unavailable."
        )

    os.environ["_ARCGIS_SALAH_REEXEC"] = "1"
    os.execv(target, [target, "-m", "arcgis_pro_salah_mcp.server", *sys.argv[1:]])
