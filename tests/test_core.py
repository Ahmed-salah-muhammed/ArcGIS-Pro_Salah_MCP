"""Core tests that run WITHOUT any ArcGIS backend (no ArcPy, no arcgis pkg).

Run:  python -m pytest tests/  (with src on PYTHONPATH or package installed)
"""
import json
from pathlib import Path

import arcgis_pro_salah_mcp as pkg
from arcgis_pro_salah_mcp._result import ok, err, guard
from arcgis_pro_salah_mcp.pro import metadata
from arcgis_pro_salah_mcp.webapp import generator
from arcgis_pro_salah_mcp.webapp import dashboard


def test_version():
    assert pkg.__version__


def test_result_envelopes():
    assert ok(123) == {"ok": True, "data": 123}
    e = err("boom", code="x")
    assert e["ok"] is False and e["error"] == "boom" and e["code"] == "x"


def test_guard_catches_exceptions():
    @guard
    def explode():
        raise ValueError("nope")

    out = explode()
    assert out["ok"] is False
    assert out["type"] == "ValueError"


def test_guard_wraps_plain_return():
    @guard
    def plain():
        return 42

    assert guard(plain)()  # callable
    assert plain() == {"ok": True, "data": 42}


def test_pro_ping_is_graceful_without_arcpy():
    # ArcPy isn't installed in CI -> guard should return an error envelope,
    # never raise.
    from arcgis_pro_salah_mcp.pro import ops as pro

    out = pro.ping()
    assert isinstance(out, dict) and "ok" in out


def test_live_ops_are_graceful_without_a_bridge(monkeypatch):
    # No ArcGIS Pro / add-in is running in CI. The live_* ops must return a
    # clean {"ok": false, "error": "bridge unreachable: ..."} envelope and never
    # raise. Point the client at a closed port so the connection is refused fast.
    from arcgis_pro_salah_mcp.config import CONFIG
    from arcgis_pro_salah_mcp.live import ops as live

    monkeypatch.setattr(CONFIG, "bridge_port", 9)  # discard port: nothing listens

    for call in (
        lambda: live.live_ping(),
        lambda: live.live_list_layers("Map"),
        lambda: live.live_zoom_to("cities"),
        lambda: live.live_query("cities", where="1=1", fields=["NAME"], limit=5),
        # confirm=True so the policy gate passes and we exercise the transport.
        lambda: live.live_run_gp("analysis.Buffer", args=["a", "b", "1 Kilometers"], confirm=True),
        lambda: live.live_add_layer("C:/data/x.shp"),
        lambda: live.live_export_layout("Layout", "C:/out/map.pdf", dpi=200),
    ):
        out = call()
        assert isinstance(out, dict) and out["ok"] is False
        assert "unreachable" in out["error"]


def test_live_client_post_returns_envelope_without_a_bridge(monkeypatch):
    from arcgis_pro_salah_mcp.config import CONFIG
    from arcgis_pro_salah_mcp.live import client

    monkeypatch.setattr(CONFIG, "bridge_port", 9)
    out = client.post("ping")
    assert out["ok"] is False and "error" in out


def test_live_readonly_mode_blocks_mutating_ops(monkeypatch):
    # In read-only mode the mutating live_* ops must refuse BEFORE any HTTP call,
    # returning a clean {"ok": false, "code": "readonly"} envelope. Point the
    # client at a dead port so a regression that lets the request through would
    # surface as "unreachable" instead of "readonly".
    from arcgis_pro_salah_mcp.config import CONFIG
    from arcgis_pro_salah_mcp.live import ops as live

    monkeypatch.setattr(CONFIG, "bridge_port", 9)
    monkeypatch.setattr(CONFIG, "bridge_readonly", True)

    for call in (
        lambda: live.live_run_gp("management.Delete", args=["x"], confirm=True),
        lambda: live.live_add_layer("C:/data/x.shp"),
        lambda: live.live_export_layout("Layout", "C:/out/map.pdf"),
    ):
        out = call()
        assert out["ok"] is False
        assert out["code"] == "readonly"
        assert "unreachable" not in out["error"]


def test_live_readonly_mode_still_allows_reads(monkeypatch):
    # Reads/navigation stay allowed in read-only mode, so they go to the bridge
    # and (with nothing listening) come back as "unreachable", not "readonly".
    from arcgis_pro_salah_mcp.config import CONFIG
    from arcgis_pro_salah_mcp.live import ops as live

    monkeypatch.setattr(CONFIG, "bridge_port", 9)
    monkeypatch.setattr(CONFIG, "bridge_readonly", True)

    for call in (
        lambda: live.live_ping(),
        lambda: live.live_list_layers("Map"),
        lambda: live.live_query("cities", where="1=1"),
        lambda: live.live_zoom_to("cities"),
    ):
        out = call()
        assert out["ok"] is False
        assert "unreachable" in out["error"]


def test_live_run_gp_requires_confirmation(monkeypatch):
    # run_gp is destructive: without confirm=True it must be refused locally,
    # even when NOT in read-only mode.
    from arcgis_pro_salah_mcp.config import CONFIG
    from arcgis_pro_salah_mcp.live import ops as live

    monkeypatch.setattr(CONFIG, "bridge_port", 9)
    monkeypatch.setattr(CONFIG, "bridge_readonly", False)

    out = live.live_run_gp("analysis.Buffer", args=["a", "b", "1 Kilometers"])
    assert out["ok"] is False and out["code"] == "confirm_required"

    # With confirm=True the gate passes and the call reaches the (dead) bridge.
    out = live.live_run_gp(
        "analysis.Buffer", args=["a", "b", "1 Kilometers"], confirm=True
    )
    assert out["ok"] is False and "unreachable" in out["error"]


def test_metadata_infers_known_themes():
    # Field names alone should reveal the domain, even with a vague layer name.
    roads = metadata.infer_theme("Layer1", ["RD_NAME", "highway_class", "speed_limit"])
    assert roads["theme"] == "transportation" and roads["score"] >= 2

    census = metadata.infer_theme(
        "tracts", ["TOTAL_POPULATION", "median_income", "household_count"]
    )
    assert census["theme"] == "demographics"

    # The layer name can carry the theme on its own.
    assert metadata.infer_theme("River_Basins", ["id", "label"])["theme"] == "hydrology"


def test_metadata_general_fallback_when_nothing_matches():
    out = metadata.infer_theme("mystery", ["foo", "bar", "baz"])
    assert out["theme"] == "general" and out["score"] == 0


def test_metadata_ignores_boring_fields_for_detection():
    # OBJECTID / Shape* must not drive detection.
    out = metadata.infer_theme("layer", ["OBJECTID", "Shape", "Shape_Area"])
    assert out["theme"] == "general"


def test_build_item_metadata_is_descriptive():
    meta = metadata.build_item_metadata(
        layer_name="city_roads",
        geometry_type="Polyline",
        field_names=["OBJECTID", "Shape_Length", "ROAD_NAME", "lanes", "speed_limit"],
        feature_count=1234,
        crs="WGS 1984",
    )
    assert "transportation" in meta["summary"].lower()
    assert "1,234" in meta["description"]
    assert "WGS 1984" in meta["description"]
    # Boring fields are not surfaced as key attributes.
    assert "OBJECTID" not in meta["description"]
    assert "ROAD_NAME" in meta["description"]
    assert "Salah MCP" in meta["tags"]
    # Tags are de-duplicated (case-insensitive).
    lowered = [t.lower() for t in meta["tags"]]
    assert len(lowered) == len(set(lowered))


def test_build_item_metadata_handles_unknown_layer():
    meta = metadata.build_item_metadata("misc", "Point", ["foo"], feature_count=3)
    assert meta["theme"] == "general"
    assert "feature layer" in meta["description"].lower()


def test_build_webmap_description_lists_layers():
    desc = metadata.build_webmap_description(
        [
            {"name": "Roads", "theme_label": "a transportation network"},
            {"name": "Rivers", "theme_label": "hydrography and water features"},
        ]
    )
    assert "Roads" in desc and "Rivers" in desc
    assert "2 layers" in desc


def test_webapp_generator_writes_description(tmp_path):
    out = generator.create_web_app(
        title="Described App",
        webmap_id="map123",
        out_dir=str(tmp_path / "desc"),
        description="A transportation network web map.",
    )
    assert out["ok"] is True
    config_js = (Path(out["data"]["output_dir"]) / "config.js").read_text(encoding="utf-8")
    assert "transportation network" in config_js


def test_webapp_generator_with_webmap(tmp_path):
    out = generator.create_web_app(
        title="Cairo Demo",
        webmap_id="abc123",
        out_dir=str(tmp_path / "app"),
        widgets=["legend", "home"],
    )
    assert out["ok"] is True
    app_dir = Path(out["data"]["output_dir"])
    for fname in ("index.html", "app.js", "config.js"):
        assert (app_dir / fname).exists()

    config_js = (app_dir / "config.js").read_text(encoding="utf-8")
    assert "abc123" in config_js
    index_html = (app_dir / "index.html").read_text(encoding="utf-8")
    assert "Cairo Demo" in index_html
    assert "__JS_SDK_VERSION__" not in index_html  # placeholder was replaced


def test_webapp_generator_requires_a_source(tmp_path):
    out = generator.create_web_app(title="x", out_dir=str(tmp_path / "a"))
    assert out["ok"] is False


def test_dashboard_generator_with_layers(tmp_path):
    out = dashboard.create_dashboard(
        title="Sales Dashboard",
        layer_item_ids=["lyr123"],
        out_dir=str(tmp_path / "dash"),
        category_field="region",
        value_fields=["revenue", "units"],
    )
    assert out["ok"] is True
    app_dir = Path(out["data"]["output_dir"])
    for fname in ("index.html", "dashboard.js", "config.js"):
        assert (app_dir / fname).exists()

    config_js = (app_dir / "config.js").read_text(encoding="utf-8")
    assert "lyr123" in config_js
    assert '"kind": "dashboard"' in config_js
    assert "region" in config_js and "revenue" in config_js

    index_html = (app_dir / "index.html").read_text(encoding="utf-8")
    assert "Sales Dashboard" in index_html
    assert "__JS_SDK_VERSION__" not in index_html  # placeholder replaced
    assert "arcgis-map" in index_html and "calcite-shell" in index_html


def test_dashboard_generator_requires_a_source(tmp_path):
    out = dashboard.create_dashboard(title="x", out_dir=str(tmp_path / "d"))
    assert out["ok"] is False


def test_dashboard_generator_rejects_bad_widget(tmp_path):
    out = dashboard.create_dashboard(
        title="x", webmap_id="id", out_dir=str(tmp_path / "e"), widgets=["bogus"]
    )
    assert out["ok"] is False


def test_webapp_generator_rejects_bad_widget(tmp_path):
    out = generator.create_web_app(
        title="x", webmap_id="id", out_dir=str(tmp_path / "b"), widgets=["nope"]
    )
    assert out["ok"] is False
