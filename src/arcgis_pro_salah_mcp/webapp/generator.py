"""Generate a static ArcGIS Maps SDK for JavaScript web app.

The output is a plain static site (no build step): ``index.html``, ``app.js``
and ``config.js``. Serve it with any static server (``python -m http.server``)
or drop it on any host. It loads either a saved Web Map by item id (which
carries its own symbology, labeling and popups), or a set of hosted feature
layers added on top of a basemap.

This module has no ArcGIS dependency, so it is fully runnable and testable
anywhere.
"""
from __future__ import annotations

import json
import shutil
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
def create_web_app(
    title: str,
    webmap_id: str | None = None,
    layer_item_ids: list[str] | None = None,
    out_dir: str | None = None,
    basemap: str = "topo-vector",
    widgets: list[str] | None = None,
    description: str | None = None,
) -> dict:
    if not webmap_id and not layer_item_ids:
        return err("Provide either webmap_id or layer_item_ids.")

    widgets = widgets or ["legend", "layerList", "home"]
    bad = set(widgets) - _VALID_WIDGETS
    if bad:
        return err(f"Unknown widget(s): {sorted(bad)}", valid=sorted(_VALID_WIDGETS))

    out = Path(out_dir or CONFIG.webapp_output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app_config = {
        "title": title,
        "description": description or "",
        "portalUrl": CONFIG.portal_url,
        "webmapId": webmap_id,
        "layerItemIds": layer_item_ids or [],
        "basemap": basemap,
        "widgets": widgets,
    }

    # config.js — values the front-end reads at runtime.
    (out / "config.js").write_text(
        "window.APP_CONFIG = " + json.dumps(app_config, indent=2) + ";\n",
        encoding="utf-8",
    )

    # index.html — CDN pinned to the configured SDK version + page title.
    index_html = (
        _template_text("index.html")
        .replace("__JS_SDK_VERSION__", CONFIG.js_sdk_version)
        .replace("__APP_TITLE__", title)
    )
    (out / "index.html").write_text(index_html, encoding="utf-8")

    # app.js — verbatim SDK logic (reads window.APP_CONFIG).
    (out / "app.js").write_text(_template_text("app.js"), encoding="utf-8")

    return ok(
        {
            "output_dir": str(out),
            "files": ["index.html", "app.js", "config.js"],
            "config": app_config,
            "serve_hint": f'cd "{out}" && python -m http.server 5500  # then open http://localhost:5500',
        }
    )


def _main() -> None:
    """stdin JSON runner for the 'Create Web App' ribbon button.

    Reads ``{"title","webmap_id","layer_item_ids","out_dir","basemap",
    "widgets","description"}`` from stdin and prints one
    ``SALAH_RESULT:<envelope-json>`` line — the same contract the C# add-in uses
    for the deploy pipeline (see webapp/github.py).
    """
    import json
    import sys

    try:
        raw = sys.stdin.read().lstrip("﻿")  # tolerate a UTF-8 BOM on stdin
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as exc:  # noqa: BLE001
        print("SALAH_RESULT:" + json.dumps(err(f"bad input: {exc}")), flush=True)
        return

    result = create_web_app(
        title=payload.get("title", "ArcGIS Web App"),
        webmap_id=payload.get("webmap_id") or None,
        layer_item_ids=payload.get("layer_item_ids") or None,
        out_dir=payload.get("out_dir") or None,
        basemap=payload.get("basemap") or "topo-vector",
        widgets=payload.get("widgets") or None,
        description=payload.get("description") or None,
    )
    print("SALAH_RESULT:" + json.dumps(result), flush=True)


if __name__ == "__main__":
    _main()
