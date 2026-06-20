"""Runtime configuration.

All values can be overridden via environment variables so the same build works
against ArcGIS Online today and an on-prem Enterprise Portal later, without code
changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# ArcGIS Online is the default portal target for v0.1.
DEFAULT_PORTAL_URL = "https://www.arcgis.com"


def _int_env(name: str, default: int) -> int:
    """Read an int from the environment, falling back to ``default`` when the
    variable is unset or not a valid integer."""
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    """Read a boolean from the environment. Truthy values (case-insensitive):
    ``1, true, yes, on``. Anything else (or unset) falls back to ``default``."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # --- Layer 2: Portal / ArcGIS Online -----------------------------------
    # The portal to connect to. Keep the default for AGOL; point it at
    # "https://<your-portal>/portal" for ArcGIS Enterprise (a later phase).
    portal_url: str = field(
        default_factory=lambda: os.environ.get("ARCGIS_PORTAL_URL", DEFAULT_PORTAL_URL)
    )
    # Preferred auth: a stored ArcGIS API for Python *profile* name, so no
    # credentials live in code or config. See README "Authentication".
    portal_profile: str | None = field(
        default_factory=lambda: os.environ.get("ARCGIS_PROFILE")
    )
    # Optional fallback (NOT recommended — prefer a profile or interactive login)
    portal_username: str | None = field(
        default_factory=lambda: os.environ.get("ARCGIS_USERNAME")
    )

    # --- Layer 1: ArcGIS Pro / ArcPy ---------------------------------------
    # Explicit path to ArcGIS Pro's python.exe (arcgispro-py3). If unset,
    # bootstrap.py will try to discover it.
    arcgis_python: str | None = field(
        default_factory=lambda: os.environ.get("CLI_ANYTHING_ARCGIS_PYTHON")
    )

    # --- Layer 1b: Live bridge (.NET add-in inside ArcGIS Pro) -------------
    # The add-in runs a loopback HTTP listener; the live_* tools POST commands
    # to it (see docs/PROTOCOL.md). Both sides read ARCGIS_BRIDGE_PORT so they
    # agree without anything hardcoded. Loopback-only (127.0.0.1), no token —
    # local use.
    bridge_port: int = field(
        default_factory=lambda: _int_env("ARCGIS_BRIDGE_PORT", 2026)
    )
    # Safety: when true, the live_* tools refuse any command that changes data,
    # the map's contents or the disk (run_gp / add_layer / export_layout). Reads
    # and navigation stay allowed so an analyst can explore the open session
    # without risk. Enforced client-side BEFORE the request reaches the bridge.
    bridge_readonly: bool = field(
        default_factory=lambda: _bool_env("ARCGIS_BRIDGE_READONLY", False)
    )

    # --- Layer 3: Web app ---------------------------------------------------
    # ArcGIS Maps SDK for JavaScript version pinned in the generated app.
    # 5.0+ ships the core API, the <arcgis-*> map components and Calcite in a
    # single CDN module bundle (see webapp/templates/index.html).
    js_sdk_version: str = field(
        default_factory=lambda: os.environ.get("ARCGIS_JS_SDK_VERSION", "5.0")
    )
    # Default output directory for generated web apps.
    webapp_output_dir: str = field(
        default_factory=lambda: os.environ.get("ARCGIS_WEBAPP_OUT", "webapp-build")
    )

    def is_enterprise(self) -> bool:
        """True when pointing at an Enterprise Portal rather than AGOL."""
        return "arcgis.com" not in self.portal_url


# Singleton-style config object imported by the tool layers.
CONFIG = Config()
