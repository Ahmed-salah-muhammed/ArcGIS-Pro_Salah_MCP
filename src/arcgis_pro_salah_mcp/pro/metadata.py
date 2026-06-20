"""Data-driven layer metadata — infer *what a layer is* from its fields & geometry.

These are pure, backend-free helpers (no ``arcpy`` / ``arcgis``), so they are
unit-testable in ``test_core.py`` and can run anywhere: inside the embedded
publish script (arcgispro-py3), behind the ``pro_describe_layer`` MCP tool, or
when building a Web Map description.

The goal is to turn a bare feature class into a human-readable ArcGIS Online
item **summary**, **description** and **tags** — "be clever about what this
layer is" — by recognising domain themes (transportation, hydrology, parcels,
demographics, …) from the layer name and its attribute field names, combined
with the geometry type.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Theme catalog. Each entry: (key, human label, keyword stems).
#
# A keyword "hits" when a field-name/layer-name token equals it, or (for stems
# of length >= 4) when a token *starts with* it. Prefix matching — not raw
# substring — keeps "age" from matching "acreage" while still catching
# "population" via "popula" or "railway" via "rail". Order matters only as a
# tie-breaker: earlier themes win an equal score.
# ---------------------------------------------------------------------------
_THEMES: list[tuple[str, str, tuple[str, ...]]] = [
    ("transportation", "a transportation network", (
        "road", "street", "highway", "route", "traffic", "rail", "railway",
        "railroad", "transit", "metro", "subway", "pavement", "lane", "aadt",
        "speed", "tunnel", "bridge", "intersection",
    )),
    ("hydrology", "hydrography and water features", (
        "river", "stream", "lake", "water", "watershed", "basin", "hydro",
        "canal", "reservoir", "wetland", "creek", "shoreline", "coast",
        "aquifer", "floodplain",
    )),
    ("buildings", "buildings and structures", (
        "building", "bldg", "structure", "stories", "storey", "floor", "roof",
        "footprint", "rooftop", "heightm", "construct",
    )),
    ("parcels", "land parcels and ownership", (
        "parcel", "apn", "zoning", "landuse", "owner", "cadastr",
        "subdivision", "acreage", "assessed", "lotsize", "ownername",
    )),
    ("boundaries", "administrative boundaries", (
        "admin", "boundary", "country", "nation", "province", "county",
        "district", "region", "municipal", "ward", "fips", "iso3", "adm0",
        "adm1", "adm2", "stateabbr", "govern",
    )),
    ("demographics", "demographics and census statistics", (
        "population", "popula", "popdens", "density", "census", "household",
        "income", "gender", "employ", "poverty", "literacy", "median",
        "ethnic",
    )),
    ("environment", "land cover and environmental data", (
        "landcover", "vegetation", "forest", "ndvi", "soil", "habitat",
        "species", "biome", "canopy", "wildlife", "ecolog",
    )),
    ("elevation", "elevation and terrain", (
        "elevation", "elev", "slope", "aspect", "contour", "altitude",
        "relief", "bathymetr", "hillshade",
    )),
    ("utilities", "a utility network", (
        "pipe", "cable", "utility", "power", "electric", "voltage",
        "sewer", "valve", "hydrant", "manhole", "transformer", "feeder",
        "watermain",
    )),
    ("hazards", "hazards and risk", (
        "flood", "hazard", "risk", "wildfire", "earthquake", "seismic",
        "landslide", "drought", "vulnerab", "exposure",
    )),
    ("health", "health facilities and public-health data", (
        "hospital", "clinic", "health", "patient", "disease", "mortality",
        "covid", "vaccine", "incidence",
    )),
    ("education", "education facilities", (
        "school", "university", "college", "student", "education", "campus",
        "enrol", "pupil",
    )),
    ("poi", "points of interest and places", (
        "amenity", "address", "category", "store", "restaurant", "hotel",
        "landmark", "facility", "venue", "business",
    )),
    ("climate", "climate and weather", (
        "temperature", "precip", "rainfall", "climate", "weather", "humidity",
        "windspeed", "pressure",
    )),
    ("geology", "geology and the subsurface", (
        "geolog", "mineral", "fault", "borehole", "litholog", "formation",
        "drillhole", "outcrop",
    )),
    ("agriculture", "agriculture and crops", (
        "crop", "farm", "yield", "irrigation", "harvest", "cultivat",
        "agricultur", "orchard",
    )),
]

# Geometry type -> the noun used to describe a feature of that shape.
_GEOM_NOUN = {
    "point": "point", "multipoint": "point",
    "polyline": "linear", "line": "linear",
    "polygon": "area", "multipatch": "3D",
}

# Field names that carry no thematic meaning — never surface them as "key
# attributes" and never let them drive theme detection.
_BORING_FIELDS = {
    "objectid", "oid", "fid", "shape", "shape_length", "shape_area",
    "shape__length", "shape__area", "globalid", "created_user", "created_date",
    "last_edited_user", "last_edited_date", "se_anno_cad_data",
}


def _tokens(text: str) -> list[str]:
    """Lower-case alphanumeric tokens from a name (splits on _, spaces, camelCase)."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text or "")
    return [t for t in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if t]


def _meaningful_fields(field_names: list[str]) -> list[str]:
    return [f for f in (field_names or []) if f and f.lower() not in _BORING_FIELDS]


def _hits(keywords: tuple[str, ...], tokens: list[str]) -> list[str]:
    """Keyword stems that match any token (exact, or prefix for stems >= 4 chars)."""
    out: set[str] = set()
    for kw in keywords:
        n = len(kw)
        if any(tok == kw or (n >= 4 and tok.startswith(kw)) for tok in tokens):
            out.add(kw)
    return sorted(out)


def infer_theme(layer_name: str, field_names: list[str]) -> dict:
    """Best-matching domain theme for a layer.

    Returns ``{"theme", "label", "score", "matched"}``. ``score`` is the number
    of distinct keyword stems that matched across the layer name and its fields;
    a score of 0 (``theme="general"``) means nothing recognisable was found.
    """
    tokens = _tokens(layer_name)
    for f in _meaningful_fields(field_names):
        tokens.extend(_tokens(f))

    best: tuple[str, str, int, list[str]] | None = None
    for key, label, keywords in _THEMES:
        matched = _hits(keywords, tokens)
        if matched and (best is None or len(matched) > best[2]):
            best = (key, label, len(matched), matched)

    if best is None:
        return {"theme": "general", "label": "a geospatial dataset", "score": 0, "matched": []}
    return {"theme": best[0], "label": best[1], "score": best[2], "matched": best[3]}


def prettify_name(name: str) -> str:
    """'road_network' / 'RoadNetwork' -> 'Road Network'."""
    words = _tokens(name)
    return " ".join(w.capitalize() for w in words) if words else (name or "Layer")


def _key_fields(field_names: list[str], limit: int = 8) -> list[str]:
    return _meaningful_fields(field_names)[:limit]


def build_item_metadata(
    layer_name: str,
    geometry_type: str | None = None,
    field_names: list[str] | None = None,
    feature_count: int | None = None,
    crs: str | None = None,
) -> dict:
    """Compose an ArcGIS Online item ``summary``, ``description`` and ``tags``
    from a layer's name, geometry, attribute fields and (optional) feature count
    and spatial reference. Pure — safe to call without any ArcGIS backend.
    """
    field_names = field_names or []
    nice = prettify_name(layer_name)
    geom = (geometry_type or "").strip()
    geom_l = geom.lower()
    noun = _GEOM_NOUN.get(geom_l, "feature")
    theme = infer_theme(layer_name, field_names)
    fields = _meaningful_fields(field_names)
    key_fields = _key_fields(field_names)

    count_txt = f"{feature_count:,} features" if isinstance(feature_count, int) else "features"
    geom_word = geom or "vector"

    # --- summary (one line, shows in item lists) ---
    if theme["score"]:
        summary = f"{nice}: {theme['label']} — {geom_word} layer ({count_txt})"
    else:
        summary = f"{nice}: {geom_word} layer ({count_txt})"

    # --- description (a few human sentences derived from the data) ---
    sentences: list[str] = []
    if theme["score"]:
        sentences.append(f"This {noun} layer represents {theme['label']}.")
    else:
        sentences.append(f"This is a {geom_word.lower()} feature layer.")

    detail = []
    if isinstance(feature_count, int):
        detail.append(f"{feature_count:,} {geom_word.lower()} features")
    if fields:
        detail.append(f"{len(fields)} attribute field" + ("s" if len(fields) != 1 else ""))
    if detail:
        tail = f" stored in {crs}" if crs else ""
        sentences.append("It contains " + " and ".join(detail) + tail + ".")
    elif crs:
        sentences.append(f"Stored in {crs}.")

    if key_fields:
        more = "" if len(fields) <= len(key_fields) else f", and {len(fields) - len(key_fields)} more"
        sentences.append("Key attributes include " + ", ".join(key_fields) + more + ".")

    sentences.append("Published from ArcGIS Pro by Salah MCP.")
    description = " ".join(sentences)

    # --- tags ---
    tags = ["Salah MCP"]
    if geom:
        tags.append(geom)
    if theme["score"]:
        # Words from the theme label that are worth indexing on.
        tags += [w.capitalize() for w in theme["label"].split()
                 if len(w) > 3 and w.lower() not in {"and", "the"}]
    tags += [w.capitalize() for w in _tokens(layer_name) if len(w) > 2]
    # De-dupe, preserve order, cap length.
    seen: set[str] = set()
    tags = [t for t in tags if not (t.lower() in seen or seen.add(t.lower()))][:12]

    return {
        "theme": theme["theme"],
        "theme_label": theme["label"],
        "summary": summary,
        "description": description,
        "tags": tags,
        "matched": theme["matched"],
    }


def build_webmap_description(layers: list[dict], title: str | None = None) -> str:
    """A description for a Web Map built from several published layers.

    ``layers`` is a list of dicts with any of ``name``/``layer``, ``theme_label``
    and ``geometry``. Produces a short paragraph naming the layers and the themes
    they cover. Pure.
    """
    layers = layers or []
    names = [l.get("name") or l.get("layer") for l in layers if (l.get("name") or l.get("layer"))]
    if not names:
        body = "This web map was assembled from layers published to ArcGIS Online."
    else:
        n = len(names)
        listing = ", ".join(names[:6]) + ("…" if n > 6 else "")
        themes = []
        for l in layers:
            tl = l.get("theme_label")
            if tl:
                tl = re.sub(r"^(a|an)\s+", "", tl)  # "a transportation network" -> "transportation network"
                if tl not in themes:
                    themes.append(tl)
        head = f"This web map brings together {n} layer{'s' if n != 1 else ''}: {listing}."
        if themes:
            theme_txt = ", ".join(themes[:4]) + ("…" if len(themes) > 4 else "")
            head += f" It covers {theme_txt}."
        body = head
    return body + " Created from ArcGIS Pro by Salah MCP."
