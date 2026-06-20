"""ArcGIS API for Python operations (Layer 2).

Talks to ArcGIS Online (default) or an Enterprise Portal. The active ``GIS``
connection is held at module level so the agent can ``portal_connect`` once and
then call the other tools.

Authentication
--------------
Preferred: a stored *profile* (credentials saved by the arcgis package in the
OS keyring), passed as ``profile=`` or via the ``ARCGIS_PROFILE`` env var. This
keeps secrets out of code and chat. Username-only triggers an interactive
password prompt, which is not ideal for a server context — so a profile is
strongly recommended.

``arcgis`` is imported lazily so the package imports without it; install with
``pip install "arcgis-pro-salah-mcp[portal]"``.
"""
from __future__ import annotations

from typing import Any

from .._result import err, guard, ok
from ..config import CONFIG

# Active connection (set by connect()).
_GIS: Any = None


def _require_gis():
    if _GIS is None:
        raise RuntimeError("Not connected. Call portal_connect first.")
    return _GIS


def _arcgis():
    try:
        import arcgis  # type: ignore
        return arcgis
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            'ArcGIS API for Python not installed. Run: '
            'pip install "arcgis-pro-salah-mcp[portal]"'
        ) from exc


@guard
def connect(portal_url: str | None = None, profile: str | None = None, username: str | None = None) -> dict:
    """Establish the GIS connection.

    Resolution order for each parameter: explicit arg -> config/env -> default.
    """
    global _GIS
    arcgis = _arcgis()
    from arcgis.gis import GIS  # type: ignore

    url = portal_url or CONFIG.portal_url
    profile = profile or CONFIG.portal_profile
    username = username or CONFIG.portal_username

    if profile:
        _GIS = GIS(url, profile=profile)
    elif username:
        _GIS = GIS(url, username=username)  # may prompt for password
    else:
        # Anonymous access (public content only) — enough for read-only demos.
        _GIS = GIS(url)

    me = getattr(_GIS.properties, "user", None)
    return ok(
        {
            "portal": url,
            "is_enterprise": CONFIG.is_enterprise(),
            "anonymous": _GIS.users.me is None,
            "username": getattr(_GIS.users.me, "username", None),
        }
    )


@guard
def whoami() -> dict:
    gis = _require_gis()
    me = gis.users.me
    if me is None:
        return ok({"anonymous": True, "portal": gis.url})
    return ok(
        {
            "username": me.username,
            "fullName": getattr(me, "fullName", None),
            "role": getattr(me, "role", None),
            "org_id": getattr(me, "orgId", None),
            "portal": gis.url,
        }
    )


@guard
def publish_layer(source: str, title: str, tags: list[str] | None = None, folder: str | None = None) -> dict:
    """Upload a local dataset and publish it as a hosted feature layer.

    Works for shapefiles (zip), GeoPackage, CSV (with location fields),
    GeoJSON, and file geodatabase (zip). Returns the published item id.
    """
    gis = _require_gis()
    tags = tags or ["arcgis-pro-salah-mcp"]
    added = gis.content.add(
        {"title": title, "tags": ",".join(tags)},
        data=source,
        folder=folder,
    )
    published = added.publish()
    return ok(
        {
            "source_item_id": added.id,
            "item_id": published.id,
            "title": published.title,
            "type": published.type,
            "url": published.url,
            "item_url": f"{gis.url}/home/item.html?id={published.id}",
        }
    )


@guard
def search_items(query: str, item_type: str | None = None, max_items: int = 20) -> dict:
    gis = _require_gis()
    results = gis.content.search(query=query, item_type=item_type, max_items=max_items)
    return ok(
        {
            "count": len(results),
            "items": [
                {"id": it.id, "title": it.title, "type": it.type, "owner": it.owner}
                for it in results
            ],
        }
    )


@guard
def get_item(item_id: str) -> dict:
    gis = _require_gis()
    it = gis.content.get(item_id)
    if it is None:
        return err("Item not found.", item_id=item_id)
    return ok(
        {
            "id": it.id,
            "title": it.title,
            "type": it.type,
            "owner": it.owner,
            "tags": it.tags,
            "url": it.url,
            "item_url": f"{gis.url}/home/item.html?id={it.id}",
        }
    )


@guard
def create_webmap(title: str, layer_item_ids: list[str], basemap: str = "topo-vector", tags: list[str] | None = None) -> dict:
    """Create a Web Map item from one or more hosted layer items."""
    gis = _require_gis()
    from arcgis.map import Map  # type: ignore

    web_map = Map()
    web_map.basemap = basemap
    added = []
    for item_id in layer_item_ids:
        it = gis.content.get(item_id)
        if it is None:
            return err("Layer item not found.", item_id=item_id)
        web_map.content.add(it)
        added.append(item_id)

    item = web_map.save(
        item_properties={
            "title": title,
            "tags": ",".join(tags or ["arcgis-pro-salah-mcp"]),
            "snippet": "Created by ArcGIS Pro Salah MCP",
        }
    )
    return ok(
        {
            "webmap_id": item.id,
            "title": item.title,
            "layers": added,
            "item_url": f"{gis.url}/home/item.html?id={item.id}",
        }
    )


@guard
def set_layer_symbology(item_id: str, renderer: dict, layer_index: int = 0) -> dict:
    """Apply a renderer to a hosted feature layer's drawingInfo.

    ``renderer`` is an Esri renderer JSON dict (simple/uniqueValue/classBreaks).
    """
    gis = _require_gis()
    it = gis.content.get(item_id)
    if it is None:
        return err("Item not found.", item_id=item_id)
    flayer = it.layers[layer_index]
    update = {"drawingInfo": {"renderer": renderer}}
    result = flayer.manager.update_definition(update)
    return ok({"item_id": item_id, "layer_index": layer_index, "result": result})


@guard
def set_layer_labeling(item_id: str, label_field: str, layer_index: int = 0) -> dict:
    """Enable simple labeling on a hosted feature layer using a field."""
    gis = _require_gis()
    it = gis.content.get(item_id)
    if it is None:
        return err("Item not found.", item_id=item_id)
    flayer = it.layers[layer_index]
    label_class = {
        "labelExpressionInfo": {"expression": f"$feature.{label_field}"},
        "symbol": {
            "type": "esriTS",
            "color": [0, 0, 0, 255],
            "font": {"size": 10, "family": "Arial"},
        },
        "labelPlacement": "esriServerPointLabelPlacementAboveRight",
    }
    update = {"drawingInfo": {"labelingInfo": [label_class]}}
    result = flayer.manager.update_definition(update)
    return ok({"item_id": item_id, "label_field": label_field, "result": result})


@guard
def share_item(item_id: str, everyone: bool = False, org: bool = False, groups: list[str] | None = None) -> dict:
    """Share a portal item. NOTE: changing sharing is a deliberate action —
    the agent should confirm with the user before making content public."""
    gis = _require_gis()
    it = gis.content.get(item_id)
    if it is None:
        return err("Item not found.", item_id=item_id)
    result = it.sharing.sharing_level  # read current; explicit share below
    it.share(everyone=everyone, org=org, groups=groups or [])
    return ok({"item_id": item_id, "everyone": everyone, "org": org, "groups": groups or []})
