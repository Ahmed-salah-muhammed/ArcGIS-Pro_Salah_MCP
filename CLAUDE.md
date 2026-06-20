# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is
A three-layer MCP server (FastMCP) that drives ArcGIS end to end. Each layer is
a tool prefix backed by a different Esri technology:
- `pro_*`    → ArcPy (desktop geoprocessing on `.aprx` projects & `.gdb` files)
- `live_*`   → loopback HTTP to the ProSalahBridge .NET add-in inside the OPEN Pro session
- `portal_*` → ArcGIS API for Python (ArcGIS Online / Enterprise Portal)
- `webapp_*` → static ArcGIS Maps SDK for JS **5.0** generator (no backend):
  `webapp_create` (web app), `webapp_create_dashboard` (interactive dashboard),
  `webapp_github_pipeline` (deploy to GitHub + Pages)

Canonical agent workflow: **Pro (analyze) → Portal (publish) → WebApp (visualize)**.

## Commands
```bash
# Tests — must pass with NO ArcGIS installed (CI runs this)
PYTHONPATH=src python -m pytest tests/test_core.py

# A single test
PYTHONPATH=src python -m pytest tests/test_core.py::test_webapp_generator_with_webmap

# Install into ArcGIS Pro's bundled interpreter (provides ArcPy for pro_*)
"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m pip install -e .
# Add the portal_* dependency (heavy, optional):
"...\arcgispro-py3\python.exe" -m pip install -e ".[portal]"

# Run the server — ALWAYS via the entry point, never `python server.py`
arcgis-pro-salah-mcp          # package-relative imports only resolve when installed

# Build a sample.gdb to exercise the Pro tools (needs arcgispro-py3)
"...\arcgispro-py3\python.exe" demos/setup_sample.py
```

## Architecture
Two-file pattern per layer: **`ops.py` does the work, `server.py` exposes it.**
- `server.py` — the only place `@mcp.tool()` wrappers live. Each is a thin
  pass-through to an op; **its one-line docstring is the entire spec the model
  sees**, so keep docstrings accurate and self-contained.
- `pro/ops.py`, `portal/ops.py`, `webapp/generator.py` — the implementations,
  every public function `@guard`-decorated.
- `_result.py` — the `ok()` / `err()` envelope and the `guard` decorator. `guard`
  catches all exceptions into `err(...)` envelopes (so a tool never breaks the
  MCP transport), maps `NotImplementedError` → `code="not_implemented"`, and
  accepts either a raw payload (auto-wrapped in `ok()`) or a full envelope.
- `bootstrap.py` — **self-healing ArcPy discovery.** If the server starts under
  the wrong Python, it finds `arcgispro-py3` (env override → common paths →
  registry) and `os.execv`-re-executes itself there. `_ARCGIS_SALAH_REEXEC=1`
  guards against re-exec loops.
- `config.py` — `CONFIG` singleton, all env-driven (`ARCGIS_PORTAL_URL`,
  `ARCGIS_PROFILE`, `ARCGIS_JS_SDK_VERSION`, `ARCGIS_WEBAPP_OUT`,
  `CLI_ANYTHING_ARCGIS_PYTHON`). Same build targets AGOL or Enterprise.

State & backend notes:
- `portal/ops.py` holds the active `GIS` connection in a **module-level `_GIS`**.
  The agent calls `portal_connect` once; every other `portal_*` op requires it.
- `webapp/` has **no ArcGIS dependency** — `generator.py` (web app) and
  `dashboard.py` (dashboard) string-replace `__JS_SDK_VERSION__` / `__APP_TITLE__`
  in their template (`templates/index.html` or `templates/dashboard.html`), copy
  the JS verbatim (`app.js` / `dashboard.js`), and emit `config.js`
  (`window.APP_CONFIG`). Built on Maps SDK for JS **5.0** (Calcite + `<arcgis-*>`
  components; the dashboard introspects fields in the browser, so it stays
  ArcGIS-free). `github.py` deploys the generated folder. This is the only fully
  testable layer. The C# ribbon buttons shell out to `webapp.generator` /
  `webapp.dashboard` / `webapp.github` via stdin JSON → `SALAH_RESULT:` line.
- Escape hatches in `pro/ops.py`: `run_gp(tool, args, kwargs)` runs any GP tool by
  dotted name (`"analysis.Buffer"`); `execute_code(code)` execs arbitrary ArcPy.

## Conventions (follow when adding tools)
1. **Result envelope.** Return `ok(data)` / `err(msg)` from `_result`; decorate
   the op with `@guard`.
2. **Lazy backend imports.** Never import `arcpy`/`arcgis` at module top level —
   import inside `_arcpy()` / `_arcgis()` so the package imports (and
   `test_core.py` runs) on machines without ArcGIS.
3. **Tool naming.** Prefix by layer: `pro_`, `live_`, `portal_`, `webapp_`.
4. **Adding a tool:** write the `@guard` op in the relevant `ops.py`, then a thin
   `@mcp.tool()` wrapper in `server.py` with a one-line docstring.

## Key constraint
ArcPy **cannot attach to a running ArcGIS Pro session** (Esri limitation), so the
`pro_*` tools operate on `.aprx`/`.gdb` files on disk. To drive the *live* session
the `live_*` tools POST to the **ProSalahBridge** .NET add-in — a loopback HTTP
listener (port 2026, no token) running inside Pro. See `ProSalahBridge/` and
`docs/PROTOCOL.md`.

## Where the open work is
- `pro_apply_categorized_symbology` / `pro_apply_graduated_symbology` build
  `lyr.symbology` renderers (UniqueValue / GraduatedColors) — implemented.
- Web app + dashboard generators (Maps SDK 5.0), mixed Feature/Tile/Vector-Tile
  publishing, and GitHub deploy are implemented (ribbon **v0.1.2**).
- See `ROADMAP.md` for the rest (Enterprise auth, renderer-JSON builders, Vite
  output, client-side symbology overrides, live-bridge round-trip verification
  against a running ArcGIS Pro).

## Tests
`tests/test_core.py` must stay backend-free and green with no ArcGIS installed —
it asserts the envelope/guard behavior, graceful ArcPy-absent degradation, and
the webapp generator. Put any ArcGIS-dependent assertions in a separate
`test_full_e2e.py` (planned, requires ArcGIS Pro), not here.
