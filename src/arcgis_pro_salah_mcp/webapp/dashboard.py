"""Generate a static Esri-Dashboard-style web app (Layer 3).

Output is a plain static site (no build step): ``index.html``, ``dashboard.js``
and ``config.js`` — serve it with any static server or deploy it with the same
GitHub pipeline as the plain web app.

Like ``webapp/generator.py`` this module has NO ArcGIS dependency. The dashboard
is *data-driven at runtime*: ``dashboard.js`` loads the layer, reads its fields,
and builds the indicators (live counts/sums that recompute as you zoom/pan), the
category breakdown and the "features in view" list automatically. So the
generator only needs the layer source and chrome config — it stays fully
testable with no backend.
"""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from .._result import err, guard, ok
from ..config import CONFIG

_VALID_WIDGETS = {"legend", "layerList", "search", "basemapGallery", "home"}


def _template_text(name: str) -> str:
    return resources.files(__package__).joinpath("templates", name).read_text(
        encoding="utf-8"
    )


@guard
def create_dashboard(
    title: str,
    webmap_id: str | None = None,
    layer_item_ids: list[str] | None = None,
    out_dir: str | None = None,
    basemap: str = "topo-vector",
    widgets: list[str] | None = None,
    description: str | None = None,
    category_field: str | None = None,
    value_fields: list[str] | None = None,
) -> dict:
    """Generate an interactive dashboard (map + live indicators + attribute list).

    Provide either a ``webmap_id`` (its first feature layer drives the stats) or
    a list of ``layer_item_ids`` (the first is the primary stats layer; the rest
    are added to the map). ``category_field`` / ``value_fields`` are optional
    overrides — when omitted dashboard.js picks sensible fields from the data.
    """
    if not webmap_id and not layer_item_ids:
        return err("Provide either webmap_id or layer_item_ids.")

    widgets = widgets or ["legend", "layerList", "home", "search"]
    bad = set(widgets) - _VALID_WIDGETS
    if bad:
        return err(f"Unknown widget(s): {sorted(bad)}", valid=sorted(_VALID_WIDGETS))

    out = Path(out_dir or CONFIG.webapp_output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app_config = {
        "kind": "dashboard",
        "title": title,
        "description": description or "",
        "portalUrl": CONFIG.portal_url,
        "webmapId": webmap_id,
        "layerItemIds": layer_item_ids or [],
        "basemap": basemap,
        "widgets": widgets,
        "categoryField": category_field,      # optional override (else auto)
        "valueFields": value_fields or [],    # optional override (else auto)
    }

    (out / "config.js").write_text(
        "window.APP_CONFIG = " + json.dumps(app_config, indent=2) + ";\n",
        encoding="utf-8",
    )

    index_html = (
        _template_text("dashboard.html")
        .replace("__JS_SDK_VERSION__", CONFIG.js_sdk_version)
        .replace("__APP_TITLE__", title)
    )
    (out / "index.html").write_text(index_html, encoding="utf-8")
    (out / "dashboard.js").write_text(_template_text("dashboard.js"), encoding="utf-8")

    return ok(
        {
            "output_dir": str(out),
            "files": ["index.html", "dashboard.js", "config.js"],
            "config": app_config,
            "serve_hint": f'cd "{out}" && python -m http.server 5500  # then open http://localhost:5500',
        }
    )


def _main() -> None:
    """stdin JSON runner for the 'Create Dashboard' ribbon button.

    Reads ``{"title","webmap_id","layer_item_ids","out_dir","basemap","widgets",
    "description","category_field","value_fields"}`` from stdin and prints one
    ``SALAH_RESULT:<envelope-json>`` line.
    """
    import json
    import sys

    try:
        raw = sys.stdin.read().lstrip("﻿")  # tolerate a UTF-8 BOM on stdin
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as exc:  # noqa: BLE001
        print("SALAH_RESULT:" + json.dumps(err(f"bad input: {exc}")), flush=True)
        return

    result = create_dashboard(
        title=payload.get("title", "ArcGIS Dashboard"),
        webmap_id=payload.get("webmap_id") or None,
        layer_item_ids=payload.get("layer_item_ids") or None,
        out_dir=payload.get("out_dir") or None,
        basemap=payload.get("basemap") or "topo-vector",
        widgets=payload.get("widgets") or None,
        description=payload.get("description") or None,
        category_field=payload.get("category_field") or None,
        value_fields=payload.get("value_fields") or None,
    )
    print("SALAH_RESULT:" + json.dumps(result), flush=True)


if __name__ == "__main__":
    _main()
