"""ArcPy operations (Layer 1).

Design notes
------------
* ``arcpy`` is imported lazily inside ``_arcpy()`` so this module can be
  imported (and unit-tested) on machines without ArcGIS Pro. Only calling a
  tool requires ArcPy.
* Every public function is wrapped with :func:`guard`, so it always returns the
  standard ``{"ok": ...}`` envelope and never raises across the MCP boundary.
* Geoprocessing wrappers (buffer/clip/...) are fully implemented — they are
  thin one-liners over the ArcToolbox. The cartographic functions
  (symbology) build ``arcpy.mp`` renderers (UniqueValue / GraduatedColors)
  through the high-level ``lyr.symbology`` API.
"""
from __future__ import annotations

from typing import Any

from .._result import err, guard, ok


def _arcpy():
    """Lazily import and return the arcpy module (raises if unavailable)."""
    try:
        import arcpy  # type: ignore
        return arcpy
    except Exception as exc:  # pragma: no cover - depends on ArcGIS install
        raise RuntimeError(
            "ArcPy could not be imported. Run this server with ArcGIS Pro's "
            "arcgispro-py3 interpreter (see bootstrap.py)."
        ) from exc


def _project(aprx_path: str):
    return _arcpy().mp.ArcGISProject(aprx_path)


def _get_map(aprx, map_name: str | None):
    maps = aprx.listMaps()
    if not maps:
        raise ValueError("Project contains no maps.")
    if map_name:
        for m in maps:
            if m.name == map_name:
                return m
        raise ValueError(f"Map '{map_name}' not found.")
    return maps[0]


def _find_layer(m, layer_name: str):
    for lyr in m.listLayers():
        if lyr.name == layer_name:
            return lyr
    raise ValueError(f"Layer '{layer_name}' not found in map '{m.name}'.")


# --- Connection & info -----------------------------------------------------

@guard
def ping() -> dict:
    _arcpy()
    return ok("pong")


@guard
def get_info() -> dict:
    arcpy = _arcpy()
    info = arcpy.GetInstallInfo()
    return ok(
        {
            "product": info.get("ProductName"),
            "version": info.get("Version"),
            "build": info.get("BuildNumber"),
            "install_dir": info.get("InstallDir"),
            "license_level": getattr(arcpy, "ProductInfo", lambda: None)(),
        }
    )


# --- Project management ----------------------------------------------------

@guard
def project_info(aprx_path: str) -> dict:
    aprx = _project(aprx_path)
    return ok(
        {
            "path": aprx.filePath,
            "default_gdb": aprx.defaultGeodatabase,
            "maps": [m.name for m in aprx.listMaps()],
            "layouts": [lay.name for lay in aprx.listLayouts()],
        }
    )


@guard
def save_project(aprx_path: str, copy_to: str | None = None) -> dict:
    aprx = _project(aprx_path)
    if copy_to:
        aprx.saveACopy(copy_to)
        return ok({"saved_to": copy_to})
    aprx.save()
    return ok({"saved": aprx.filePath})


# --- Layer management ------------------------------------------------------

@guard
def list_layers(aprx_path: str, map_name: str | None = None) -> dict:
    aprx = _project(aprx_path)
    m = _get_map(aprx, map_name)
    layers = []
    for lyr in m.listLayers():
        layers.append(
            {
                "name": lyr.name,
                "is_feature": getattr(lyr, "isFeatureLayer", False),
                "is_raster": getattr(lyr, "isRasterLayer", False),
                "visible": getattr(lyr, "visible", None),
            }
        )
    return ok({"map": m.name, "layers": layers})


@guard
def add_layer(aprx_path: str, data_path: str, map_name: str | None = None) -> dict:
    aprx = _project(aprx_path)
    m = _get_map(aprx, map_name)
    m.addDataFromPath(data_path)
    aprx.save()
    return ok({"added": data_path, "map": m.name})


@guard
def remove_layer(aprx_path: str, layer_name: str, map_name: str | None = None) -> dict:
    aprx = _project(aprx_path)
    m = _get_map(aprx, map_name)
    lyr = _find_layer(m, layer_name)
    m.removeLayer(lyr)
    aprx.save()
    return ok({"removed": layer_name})


@guard
def rename_layer(aprx_path: str, layer_name: str, new_name: str, map_name: str | None = None) -> dict:
    aprx = _project(aprx_path)
    m = _get_map(aprx, map_name)
    lyr = _find_layer(m, layer_name)
    lyr.name = new_name
    aprx.save()
    return ok({"renamed_to": new_name})


@guard
def set_visibility(aprx_path: str, layer_name: str, visible: bool, map_name: str | None = None) -> dict:
    aprx = _project(aprx_path)
    m = _get_map(aprx, map_name)
    lyr = _find_layer(m, layer_name)
    lyr.visible = bool(visible)
    aprx.save()
    return ok({"layer": layer_name, "visible": bool(visible)})


@guard
def layer_summary(dataset: str) -> dict:
    arcpy = _arcpy()
    desc = arcpy.Describe(dataset)
    count = int(arcpy.management.GetCount(dataset)[0])
    fields = [{"name": f.name, "type": f.type} for f in arcpy.ListFields(dataset)]
    sr = getattr(desc, "spatialReference", None)
    return ok(
        {
            "feature_count": count,
            "geometry_type": getattr(desc, "shapeType", None),
            "crs": getattr(sr, "name", None) if sr else None,
            "fields": fields,
        }
    )


@guard
def describe_layer(dataset: str, layer_name: str | None = None) -> dict:
    """Infer what a layer *is* from its geometry and field names, returning a
    ready-to-use ArcGIS Online item summary/description/tags (see metadata.py)."""
    from . import metadata

    arcpy = _arcpy()
    desc = arcpy.Describe(dataset)
    count = int(arcpy.management.GetCount(dataset)[0])
    field_names = [f.name for f in arcpy.ListFields(dataset)]
    sr = getattr(desc, "spatialReference", None)
    meta = metadata.build_item_metadata(
        layer_name=layer_name or getattr(desc, "name", None) or "Layer",
        geometry_type=getattr(desc, "shapeType", None),
        field_names=field_names,
        feature_count=count,
        crs=getattr(sr, "name", None) if sr else None,
    )
    return ok(meta)


# --- Features & attributes -------------------------------------------------

@guard
def get_features(dataset: str, fields: list[str] | None = None, limit: int = 10) -> dict:
    arcpy = _arcpy()
    field_list = fields or [f.name for f in arcpy.ListFields(dataset)]
    rows: list[dict] = []
    with arcpy.da.SearchCursor(dataset, field_list) as cursor:
        for i, row in enumerate(cursor):
            if i >= limit:
                break
            rows.append(dict(zip(field_list, [str(v) for v in row])))
    return ok({"fields": field_list, "rows": rows, "returned": len(rows)})


@guard
def select_by_expression(layer: str, where_clause: str) -> dict:
    arcpy = _arcpy()
    result = arcpy.management.SelectLayerByAttribute(layer, "NEW_SELECTION", where_clause)
    selected = int(arcpy.management.GetCount(result)[0])
    return ok({"selected": selected, "where": where_clause})


@guard
def add_field(dataset: str, field_name: str, field_type: str = "TEXT") -> dict:
    arcpy = _arcpy()
    arcpy.management.AddField(dataset, field_name, field_type)
    return ok({"added_field": field_name, "type": field_type})


@guard
def calculate_field(dataset: str, field: str, expression: str) -> dict:
    arcpy = _arcpy()
    arcpy.management.CalculateField(dataset, field, expression, "PYTHON3")
    return ok({"field": field, "expression": expression})


@guard
def field_statistics(dataset: str, field_name: str) -> dict:
    arcpy = _arcpy()
    import statistics as _stats

    values = [
        r[0]
        for r in arcpy.da.SearchCursor(dataset, [field_name])
        if r[0] is not None
    ]
    if not values:
        return err("No non-null values found.", field=field_name)
    return ok(
        {
            "field": field_name,
            "count": len(values),
            "sum": sum(values),
            "mean": _stats.fmean(values),
            "median": _stats.median(values),
            "stdev": _stats.pstdev(values),
            "min": min(values),
            "max": max(values),
        }
    )


# --- Spatial analysis (fully implemented thin wrappers) --------------------

@guard
def buffer(dataset: str, out: str, distance: str) -> dict:
    _arcpy().analysis.Buffer(dataset, out, distance)
    return ok({"output": out, "distance": distance})


@guard
def clip(dataset: str, mask: str, out: str) -> dict:
    _arcpy().analysis.Clip(dataset, mask, out)
    return ok({"output": out})


@guard
def spatial_join(target: str, join: str, out: str) -> dict:
    _arcpy().analysis.SpatialJoin(target, join, out)
    return ok({"output": out})


@guard
def dissolve(dataset: str, out: str, field: str | None = None) -> dict:
    _arcpy().management.Dissolve(dataset, out, field)
    return ok({"output": out, "dissolve_field": field})


@guard
def merge(datasets: list[str], out: str) -> dict:
    _arcpy().management.Merge(datasets, out)
    return ok({"output": out, "inputs": datasets})


@guard
def reproject(dataset: str, out: str, target_crs: str) -> dict:
    arcpy = _arcpy()
    # Accept "EPSG:4326" or a WKID like "4326".
    wkid = int(target_crs.split(":")[-1])
    sr = arcpy.SpatialReference(wkid)
    arcpy.management.Project(dataset, out, sr)
    return ok({"output": out, "crs": target_crs})


@guard
def repair_geometry(dataset: str) -> dict:
    _arcpy().management.RepairGeometry(dataset)
    return ok({"repaired": dataset})


@guard
def extract(dataset: str, where_clause: str, out: str) -> dict:
    _arcpy().analysis.Select(dataset, out, where_clause)
    return ok({"output": out, "where": where_clause})


# --- Symbology (cartographic authoring) ------------------------------------

def _pick_color_ramp(aprx, *names):
    """Return the first ColorRamp matching any of the given name wildcards.

    Falls back to the project's first available ramp, or ``None`` if the install
    exposes none. ``listColorRamps`` is tolerant of a missing wildcard, so empty
    / ``None`` entries are skipped — that lets callers pass an optional
    user-supplied name first and sensible defaults after it.
    """
    for name in names:
        if not name:
            continue
        ramps = aprx.listColorRamps(name)
        if ramps:
            return ramps[0]
    ramps = aprx.listColorRamps()
    return ramps[0] if ramps else None


@guard
def apply_categorized_symbology(aprx_path: str, layer_name: str, field_name: str, map_name: str | None = None) -> dict:
    """Unique-value (categorized) renderer: one symbol per distinct field value."""
    aprx = _project(aprx_path)
    m = _get_map(aprx, map_name)
    lyr = _find_layer(m, layer_name)
    if not getattr(lyr, "isFeatureLayer", False):
        return err("Categorized symbology requires a feature layer.", layer=layer_name)

    sym = lyr.symbology
    if not hasattr(sym, "updateRenderer"):
        return err("Layer does not expose a symbology renderer.", layer=layer_name)

    # Switch the renderer type, then assigning the field makes ArcPy enumerate
    # the distinct values from the data source and build one class each.
    sym.updateRenderer("UniqueValueRenderer")
    sym.renderer.fields = [field_name]
    ramp = _pick_color_ramp(aprx, "Basic Random", "Random")
    if ramp is not None:
        sym.renderer.colorRamp = ramp
    lyr.symbology = sym          # commit the renderer back onto the layer
    aprx.save()

    # Re-read the committed renderer to report the categories ArcPy generated.
    renderer = lyr.symbology.renderer
    labels = [
        item.label
        for group in getattr(renderer, "groups", [])
        for item in getattr(group, "items", [])
    ]
    return ok(
        {
            "layer": layer_name,
            "renderer": "UniqueValueRenderer",
            "field": field_name,
            "color_ramp": getattr(ramp, "name", None),
            "category_count": len(labels),
            "categories": labels[:50],   # cap the echo for high-cardinality fields
        }
    )


@guard
def apply_graduated_symbology(aprx_path: str, layer_name: str, field_name: str, classes: int = 5, color_ramp: str | None = None, map_name: str | None = None) -> dict:
    """Graduated-colors (choropleth) renderer over a numeric field."""
    aprx = _project(aprx_path)
    m = _get_map(aprx, map_name)
    lyr = _find_layer(m, layer_name)
    if not getattr(lyr, "isFeatureLayer", False):
        return err("Graduated symbology requires a feature layer.", layer=layer_name)

    # Graduated colors classify a continuous range, so the field must be numeric.
    # Best-effort check against the data source — skip silently if it's unreadable.
    ftype = None
    try:
        fields = _arcpy().ListFields(lyr.dataSource, field_name)
        ftype = fields[0].type if fields else None
    except Exception:  # pragma: no cover - depends on the live data source
        ftype = None
    if ftype is not None and ftype not in {"SmallInteger", "Integer", "BigInteger", "Single", "Double"}:
        return err(
            f"Field '{field_name}' is {ftype}; graduated symbology needs a numeric field.",
            layer=layer_name,
        )

    classes = max(1, int(classes))
    sym = lyr.symbology
    if not hasattr(sym, "updateRenderer"):
        return err("Layer does not expose a symbology renderer.", layer=layer_name)

    sym.updateRenderer("GraduatedColorsRenderer")
    sym.renderer.classificationField = field_name
    sym.renderer.breakCount = classes
    ramp = _pick_color_ramp(aprx, color_ramp, "Yellow to Red", "Oranges (Continuous)", "Reds (Continuous)")
    if ramp is not None:
        sym.renderer.colorRamp = ramp
    lyr.symbology = sym          # commit the renderer back onto the layer
    aprx.save()

    # Re-read the committed renderer to report the class breaks ArcPy computed.
    renderer = lyr.symbology.renderer
    breaks = [
        {"upper_bound": cb.upperBound, "label": cb.label}
        for cb in getattr(renderer, "classBreaks", [])
    ]
    return ok(
        {
            "layer": layer_name,
            "renderer": "GraduatedColorsRenderer",
            "field": field_name,
            "color_ramp": getattr(ramp, "name", None),
            "classes": len(breaks) or classes,
            "breaks": breaks,
        }
    )


@guard
def set_opacity(aprx_path: str, layer_name: str, opacity: float, map_name: str | None = None) -> dict:
    aprx = _project(aprx_path)
    m = _get_map(aprx, map_name)
    lyr = _find_layer(m, layer_name)
    # ArcPy uses transparency 0-100 (0 = opaque) — inverse of opacity 0..1.
    lyr.transparency = int(round((1.0 - float(opacity)) * 100))
    aprx.save()
    return ok({"layer": layer_name, "opacity": opacity, "transparency": lyr.transparency})


# --- Export ----------------------------------------------------------------

@guard
def export_layer(dataset: str, out_path: str) -> dict:
    _arcpy().conversion.ExportFeatures(dataset, out_path)
    return ok({"output": out_path})


def _get_layout(aprx, layout_name: str):
    for lay in aprx.listLayouts():
        if lay.name == layout_name:
            return lay
    raise ValueError(f"Layout '{layout_name}' not found.")


@guard
def export_image(aprx_path: str, layout_name: str, out_path: str, dpi: int = 150) -> dict:
    aprx = _project(aprx_path)
    layout = _get_layout(aprx, layout_name)
    if out_path.lower().endswith((".jpg", ".jpeg")):
        layout.exportToJPEG(out_path, resolution=dpi)
    else:
        layout.exportToPNG(out_path, resolution=dpi)
    return ok({"output": out_path, "dpi": dpi})


@guard
def export_pdf(aprx_path: str, layout_name: str, out_path: str, dpi: int = 300) -> dict:
    aprx = _project(aprx_path)
    layout = _get_layout(aprx, layout_name)
    layout.exportToPDF(out_path, resolution=dpi)
    return ok({"output": out_path, "dpi": dpi})


@guard
def export_map_series(aprx_path: str, layout_name: str, out_path: str) -> dict:
    aprx = _project(aprx_path)
    layout = _get_layout(aprx, layout_name)
    ms = getattr(layout, "mapSeries", None)
    if not ms or not ms.enabled:
        return err("Layout has no enabled Map Series.", layout=layout_name)
    ms.exportToPDF(out_path)
    return ok({"output": out_path, "pages": ms.pageCount})


# --- Generic geoprocessing + escape hatch ----------------------------------

@guard
def run_gp(tool: str, args: list[Any] | None = None, kwargs: dict | None = None) -> dict:
    """Run any GP tool by dotted name, e.g. 'analysis.Buffer'."""
    arcpy = _arcpy()
    args = args or []
    kwargs = kwargs or {}
    module_name, _, func_name = tool.rpartition(".")
    target = arcpy
    for part in module_name.split(".") if module_name else []:
        target = getattr(target, part)
    func = getattr(target, func_name)
    result = func(*args, **kwargs)
    # Result objects stringify to their output path(s).
    outputs = [result[i] for i in range(result.outputCount)] if hasattr(result, "outputCount") else [str(result)]
    return ok({"tool": tool, "outputs": outputs})


@guard
def execute_code(code: str) -> dict:
    """Run arbitrary ArcPy code. `arcpy` is pre-imported into the namespace."""
    arcpy = _arcpy()
    import io
    import contextlib

    namespace: dict[str, Any] = {"arcpy": arcpy}
    buffer_out = io.StringIO()
    with contextlib.redirect_stdout(buffer_out):
        exec(code, namespace)  # noqa: S102 - intentional escape hatch
    return ok({"stdout": buffer_out.getvalue()})
