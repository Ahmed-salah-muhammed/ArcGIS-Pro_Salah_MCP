"""FastMCP server — wires the three tool layers to Claude.

Run via the installed entry point (recommended), NOT by passing this file to
python directly (package-relative imports would break):

    arcgis-pro-salah-mcp

Tool naming convention:
    pro_*     -> Layer 1,  ArcGIS Pro / ArcPy (desktop, .aprx & geodatabases)
    live_*    -> Layer 1b, the OPEN ArcGIS Pro session via the .NET bridge
    portal_*  -> Layer 2,  ArcGIS API for Python (ArcGIS Online / Enterprise)
    webapp_*  -> Layer 3,  ArcGIS Maps SDK for JavaScript app generator
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__
from .pro import ops as pro
from .live import ops as live
from .portal import ops as portal
from .webapp import generator as webapp
from .webapp import dashboard as webapp_dashboard
from .webapp import github as webapp_github

INSTRUCTIONS = """\
Drive the full ArcGIS stack end to end. A typical workflow is:
  1. pro_*    — prepare/analyze data in ArcGIS Pro with ArcPy (buffer, clip, ...)
  2. portal_* — publish the result to ArcGIS Online/Portal and build a web map
  3. webapp_* — generate a static ArcGIS Maps SDK for JS app showing the layers
Every tool returns {"ok": true, "data": ...} or {"ok": false, "error": ...}.
"""

mcp = FastMCP("ArcGIS_Pro_Salah_MCP", instructions=INSTRUCTIONS)


# =====================================================================
# Layer 1 — ArcGIS Pro / ArcPy
# =====================================================================

@mcp.tool()
def pro_ping() -> dict:
    """Check that ArcPy is reachable in the running interpreter."""
    return pro.ping()


@mcp.tool()
def pro_get_info() -> dict:
    """ArcGIS Pro / ArcPy version, build and license level."""
    return pro.get_info()


@mcp.tool()
def pro_project_info(aprx_path: str) -> dict:
    """Read an .aprx project: maps, layouts, default geodatabase, CRS."""
    return pro.project_info(aprx_path)


@mcp.tool()
def pro_save_project(aprx_path: str, copy_to: str | None = None) -> dict:
    """Save the project, optionally to a new path (saveACopy)."""
    return pro.save_project(aprx_path, copy_to)


@mcp.tool()
def pro_list_layers(aprx_path: str, map_name: str | None = None) -> dict:
    """List layers in a map (name, type, CRS, visibility)."""
    return pro.list_layers(aprx_path, map_name)


@mcp.tool()
def pro_add_layer(aprx_path: str, data_path: str, map_name: str | None = None) -> dict:
    """Add a vector or raster dataset to a map (addDataFromPath)."""
    return pro.add_layer(aprx_path, data_path, map_name)


@mcp.tool()
def pro_remove_layer(aprx_path: str, layer_name: str, map_name: str | None = None) -> dict:
    """Remove a layer from a map."""
    return pro.remove_layer(aprx_path, layer_name, map_name)


@mcp.tool()
def pro_rename_layer(aprx_path: str, layer_name: str, new_name: str, map_name: str | None = None) -> dict:
    """Rename a layer."""
    return pro.rename_layer(aprx_path, layer_name, new_name, map_name)


@mcp.tool()
def pro_set_visibility(aprx_path: str, layer_name: str, visible: bool, map_name: str | None = None) -> dict:
    """Show or hide a layer."""
    return pro.set_visibility(aprx_path, layer_name, visible, map_name)


@mcp.tool()
def pro_layer_summary(dataset: str) -> dict:
    """Feature count, fields, geometry type and CRS for a dataset."""
    return pro.layer_summary(dataset)


@mcp.tool()
def pro_describe_layer(dataset: str, layer_name: str | None = None) -> dict:
    """Detect what a layer is from its fields/geometry; returns a smart item summary, description and tags."""
    return pro.describe_layer(dataset, layer_name)


@mcp.tool()
def pro_get_features(dataset: str, fields: list[str] | None = None, limit: int = 10) -> dict:
    """Return attribute rows from a feature class/table (SearchCursor)."""
    return pro.get_features(dataset, fields, limit)


@mcp.tool()
def pro_select_by_expression(layer: str, where_clause: str) -> dict:
    """Select features matching a SQL where-clause (SelectLayerByAttribute)."""
    return pro.select_by_expression(layer, where_clause)


@mcp.tool()
def pro_add_field(dataset: str, field_name: str, field_type: str = "TEXT") -> dict:
    """Add an attribute field (TEXT/SHORT/LONG/DOUBLE/DATE)."""
    return pro.add_field(dataset, field_name, field_type)


@mcp.tool()
def pro_calculate_field(dataset: str, field: str, expression: str) -> dict:
    """Compute a field's values with a Python expression (CalculateField)."""
    return pro.calculate_field(dataset, field, expression)


@mcp.tool()
def pro_field_statistics(dataset: str, field_name: str) -> dict:
    """count/sum/mean/median/std/min/max for a numeric field."""
    return pro.field_statistics(dataset, field_name)


@mcp.tool()
def pro_buffer(dataset: str, out: str, distance: str) -> dict:
    """Buffer features by a distance, e.g. '100 Meters' (analysis.Buffer)."""
    return pro.buffer(dataset, out, distance)


@mcp.tool()
def pro_clip(dataset: str, mask: str, out: str) -> dict:
    """Clip a layer to the boundary of another (analysis.Clip)."""
    return pro.clip(dataset, mask, out)


@mcp.tool()
def pro_spatial_join(target: str, join: str, out: str) -> dict:
    """Join attributes by spatial intersection (analysis.SpatialJoin)."""
    return pro.spatial_join(target, join, out)


@mcp.tool()
def pro_dissolve(dataset: str, out: str, field: str | None = None) -> dict:
    """Merge features, optionally grouped by a field (management.Dissolve)."""
    return pro.dissolve(dataset, out, field)


@mcp.tool()
def pro_merge(datasets: list[str], out: str) -> dict:
    """Combine multiple layers of the same geometry type (management.Merge)."""
    return pro.merge(datasets, out)


@mcp.tool()
def pro_reproject(dataset: str, out: str, target_crs: str) -> dict:
    """Reproject to a CRS, e.g. 'EPSG:4326' (management.Project)."""
    return pro.reproject(dataset, out, target_crs)


@mcp.tool()
def pro_repair_geometry(dataset: str) -> dict:
    """Fix invalid geometries in place (management.RepairGeometry)."""
    return pro.repair_geometry(dataset)


@mcp.tool()
def pro_extract(dataset: str, where_clause: str, out: str) -> dict:
    """Extract matching features into a new dataset (analysis.Select)."""
    return pro.extract(dataset, where_clause, out)


@mcp.tool()
def pro_apply_categorized_symbology(aprx_path: str, layer_name: str, field_name: str, map_name: str | None = None) -> dict:
    """Unique-value symbology: a distinct colour per field value."""
    return pro.apply_categorized_symbology(aprx_path, layer_name, field_name, map_name)


@mcp.tool()
def pro_apply_graduated_symbology(aprx_path: str, layer_name: str, field_name: str, classes: int = 5, color_ramp: str | None = None, map_name: str | None = None) -> dict:
    """Graduated (choropleth) symbology on a numeric field."""
    return pro.apply_graduated_symbology(aprx_path, layer_name, field_name, classes, color_ramp, map_name)


@mcp.tool()
def pro_set_opacity(aprx_path: str, layer_name: str, opacity: float, map_name: str | None = None) -> dict:
    """Set layer opacity 0.0-1.0 (converted to ArcPy transparency 0-100)."""
    return pro.set_opacity(aprx_path, layer_name, opacity, map_name)


@mcp.tool()
def pro_export_layer(dataset: str, out_path: str) -> dict:
    """Export a layer/feature class to a file (format from extension)."""
    return pro.export_layer(dataset, out_path)


@mcp.tool()
def pro_export_image(aprx_path: str, layout_name: str, out_path: str, dpi: int = 150) -> dict:
    """Export a layout to PNG/JPG."""
    return pro.export_image(aprx_path, layout_name, out_path, dpi)


@mcp.tool()
def pro_export_pdf(aprx_path: str, layout_name: str, out_path: str, dpi: int = 300) -> dict:
    """Export a layout to PDF."""
    return pro.export_pdf(aprx_path, layout_name, out_path, dpi)


@mcp.tool()
def pro_export_map_series(aprx_path: str, layout_name: str, out_path: str) -> dict:
    """Export a layout's Map Series / map book to a multi-page PDF."""
    return pro.export_map_series(aprx_path, layout_name, out_path)


@mcp.tool()
def pro_run_gp(tool: str, args: list[Any] | None = None, kwargs: dict | None = None) -> dict:
    """Run ANY geoprocessing tool by name, e.g. 'analysis.Buffer'."""
    return pro.run_gp(tool, args, kwargs)


@mcp.tool()
def pro_execute_code(code: str) -> dict:
    """Escape hatch: run arbitrary ArcPy Python. `arcpy` is pre-imported."""
    return pro.execute_code(code)


# =====================================================================
# Layer 1b — Live session (the OPEN ArcGIS Pro session via the .NET bridge)
# =====================================================================
# These tools POST commands over loopback HTTP to the ProSalahBridge add-in
# running inside ArcGIS Pro (see ProSalahBridge/ and docs/PROTOCOL.md). If Pro or
# the add-in isn't running they return a clean {"ok": false, "error": "bridge
# unreachable: ..."} envelope rather than failing.

@mcp.tool()
def live_ping() -> dict:
    """Liveness + context of the OPEN ArcGIS Pro session (project, maps, layouts)."""
    return live.live_ping()


@mcp.tool()
def live_list_layers(map_name: str | None = None) -> dict:
    """List layers in the active (or named) map of the open Pro session."""
    return live.live_list_layers(map_name)


@mcp.tool()
def live_zoom_to(layer: str, selection: bool = False) -> dict:
    """Zoom the active view to a layer (or its current selection)."""
    return live.live_zoom_to(layer, selection)


@mcp.tool()
def live_query(layer: str, where: str | None = None, fields: list[str] | None = None, limit: int = 10) -> dict:
    """Read attribute rows from a layer in the open Pro session."""
    return live.live_query(layer, where, fields, limit)


@mcp.tool()
def live_run_gp(tool: str, args: list[Any] | None = None, kwargs: dict | None = None, confirm: bool = False) -> dict:
    """Run a geoprocessing tool LIVE; output is added to the active map. Destructive: pass confirm=True (refused in read-only mode)."""
    return live.live_run_gp(tool, args, kwargs, confirm)


@mcp.tool()
def live_add_layer(path: str) -> dict:
    """Add a dataset from disk to the active map of the open Pro session (refused in read-only mode)."""
    return live.live_add_layer(path)


@mcp.tool()
def live_export_layout(layout: str, out_path: str, dpi: int = 300) -> dict:
    """Export a layout from the open Pro session to a PDF (refused in read-only mode)."""
    return live.live_export_layout(layout, out_path, dpi)


@mcp.tool()
def live_get_request(clear: bool = False) -> dict:
    """Fetch what the user queued from the Salah MCP ribbon (Create Web App prompt / Publish). clear=True consumes it."""
    return live.live_get_request(clear)


# =====================================================================
# Layer 2 — Portal / ArcGIS Online (ArcGIS API for Python)
# =====================================================================

@mcp.tool()
def portal_connect(portal_url: str | None = None, profile: str | None = None, username: str | None = None) -> dict:
    """Connect to ArcGIS Online/Portal. Prefer a stored profile over username."""
    return portal.connect(portal_url, profile, username)


@mcp.tool()
def portal_whoami() -> dict:
    """Return the signed-in user, org and portal URL."""
    return portal.whoami()


@mcp.tool()
def portal_publish_layer(source: str, title: str, tags: list[str] | None = None, folder: str | None = None) -> dict:
    """Publish a local dataset (shp/gpkg/feature class/CSV) as a hosted feature layer. Returns the item id."""
    return portal.publish_layer(source, title, tags, folder)


@mcp.tool()
def portal_search_items(query: str, item_type: str | None = None, max_items: int = 20) -> dict:
    """Search the portal for items."""
    return portal.search_items(query, item_type, max_items)


@mcp.tool()
def portal_get_item(item_id: str) -> dict:
    """Get metadata for a portal item by id."""
    return portal.get_item(item_id)


@mcp.tool()
def portal_create_webmap(title: str, layer_item_ids: list[str], basemap: str = "topo-vector", tags: list[str] | None = None) -> dict:
    """Create a Web Map from one or more hosted layer item ids. Returns the webmap item id."""
    return portal.create_webmap(title, layer_item_ids, basemap, tags)


@mcp.tool()
def portal_set_layer_symbology(item_id: str, renderer: dict, layer_index: int = 0) -> dict:
    """Apply a renderer (symbology) to a hosted feature layer's drawing info."""
    return portal.set_layer_symbology(item_id, renderer, layer_index)


@mcp.tool()
def portal_set_layer_labeling(item_id: str, label_field: str, layer_index: int = 0) -> dict:
    """Enable labeling on a hosted feature layer using a field."""
    return portal.set_layer_labeling(item_id, label_field, layer_index)


@mcp.tool()
def portal_share_item(item_id: str, everyone: bool = False, org: bool = False, groups: list[str] | None = None) -> dict:
    """Share a portal item with everyone / the org / specific groups."""
    return portal.share_item(item_id, everyone, org, groups)


# =====================================================================
# Layer 3 — Web app generator (ArcGIS Maps SDK for JavaScript, static)
# =====================================================================

@mcp.tool()
def webapp_create(title: str, webmap_id: str | None = None, layer_item_ids: list[str] | None = None, out_dir: str | None = None, basemap: str = "topo-vector", widgets: list[str] | None = None) -> dict:
    """Generate a static ArcGIS Maps SDK for JS app.

    Provide either a `webmap_id` (loads a saved Web Map with its symbology &
    labeling) or a list of `layer_item_ids` (added as feature layers).
    `widgets` may include: legend, layerList, search, basemapGallery, home.
    """
    return webapp.create_web_app(title, webmap_id, layer_item_ids, out_dir, basemap, widgets)


@mcp.tool()
def webapp_create_dashboard(title: str, webmap_id: str | None = None, layer_item_ids: list[str] | None = None, out_dir: str | None = None, basemap: str = "topo-vector", widgets: list[str] | None = None, category_field: str | None = None, value_fields: list[str] | None = None) -> dict:
    """Generate a static Esri-Dashboard-style web app (map + live indicators + attribute list).

    Provide either a `webmap_id` (its first feature layer drives the stats) or
    `layer_item_ids` (the first is the primary stats layer). Indicators (count &
    sums), a category breakdown and a "features in view" list are derived from the
    data at runtime and recompute as you zoom/pan. `category_field` / `value_fields`
    optionally override the auto-picked fields.
    """
    return webapp_dashboard.create_dashboard(title, webmap_id, layer_item_ids, out_dir, basemap, widgets, None, category_field, value_fields)


@mcp.tool()
def webapp_github_pipeline(repo_name: str, token: str, deploy_mode: str = "upload") -> dict:
    """Create a public GitHub repo, push the generated static web app, and (deploy_mode='live') enable GitHub Pages."""
    return webapp_github.github_pipeline(repo_name, token, deploy_mode)


def main() -> None:
    """Console-script entry point."""
    mcp.run()


if __name__ == "__main__":
    main()
