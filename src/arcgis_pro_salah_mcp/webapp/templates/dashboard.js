/* ArcGIS Maps SDK for JavaScript 5.0 — interactive dashboard logic.
 *
 * Esri-Dashboard-style behaviour, fully data-driven: load the primary feature
 * layer, read its fields, and build
 *   - indicator cards  (total count + sums of numeric fields)
 *   - a category breakdown (bar list)
 *   - a "features in view" list (click to fly + highlight + popup)
 * Every indicator/breakdown/list recomputes for the map's CURRENT extent each
 * time the view stops moving — so zooming and panning update the numbers.
 *
 * Reads window.APP_CONFIG (config.js). Core classes load via $arcgis.import().
 */
(async function () {
  "use strict";

  var cfg = window.APP_CONFIG || {};
  var NUMERIC = { "double": 1, "integer": 1, "single": 1, "small-integer": 1, "long": 1 };

  await customElements.whenDefined("arcgis-map");
  var mapEl = document.querySelector("arcgis-map");
  if (!mapEl) return;

  var logo = document.getElementById("appLogo");
  if (logo && cfg.description) logo.description = cfg.description;
  var chip = document.getElementById("extentChip");

  setupTheme();   // Light/Dark radio toggle (Calcite chrome + ArcGIS widgets)

  // -------------------------------------------------------------------------
  //  Light / Dark theme — toggles the Calcite mode class on <body> and swaps
  //  the ArcGIS theme stylesheet so the map widgets follow too.
  // -------------------------------------------------------------------------
  function applyTheme(mode) {
    var dark = mode === "dark";
    document.body.classList.toggle("calcite-mode-dark", dark);
    document.body.classList.toggle("calcite-mode-light", !dark);
    var link = document.getElementById("esriTheme");
    if (link) {
      link.href = link.href.replace(/\/themes\/(light|dark)\//,
        "/themes/" + (dark ? "dark" : "light") + "/");
    }
  }

  function setupTheme() {
    var group = document.getElementById("themeToggle");
    if (!group) return;
    function current() {
      var sel = group.querySelector("calcite-radio-button[checked]");
      return sel ? sel.value : "light";
    }
    var onChange = function (e) {
      var v = (e && e.target && e.target.selectedItem && e.target.selectedItem.value) || current();
      applyTheme(v);
    };
    group.addEventListener("calciteRadioButtonGroupChange", onChange);
    // Fallback for Calcite builds that only emit per-button change events.
    group.querySelectorAll("calcite-radio-button").forEach(function (rb) {
      rb.addEventListener("calciteRadioButtonChange", onChange);
    });
    applyTheme(current());   // honour the initially-checked option
  }

  // Keep only the configured widgets.
  var WIDGET_IDS = { home: "w-home", search: "w-search", legend: "w-legend",
                     layerList: "w-layerlist", basemapGallery: "w-basemap" };
  var on = {}; (cfg.widgets || []).forEach(function (w) { on[w] = true; });
  Object.keys(WIDGET_IDS).forEach(function (n) {
    if (!on[n]) { var e = document.getElementById(WIDGET_IDS[n]); if (e) e.remove(); }
  });

  var mods = await $arcgis.import([
    "@arcgis/core/config.js",
    "@arcgis/core/layers/FeatureLayer.js",
    "@arcgis/core/core/reactiveUtils.js",
  ]);
  var esriConfig = mods[0], FeatureLayer = mods[1], reactiveUtils = mods[2];
  if (cfg.portalUrl) { try { esriConfig.portalUrl = cfg.portalUrl; } catch (e) {} }

  // --- map source -----------------------------------------------------------
  if (cfg.webmapId) {
    mapEl.itemId = cfg.webmapId;
  } else {
    mapEl.basemap = cfg.basemap || "topo-vector";
  }
  await viewReady(mapEl);
  var view = mapEl.view, map = mapEl.map;

  if (!cfg.webmapId) {
    (cfg.layerItemIds || []).forEach(function (id) {
      map.add(new FeatureLayer({ portalItem: { id: id } }));
    });
  }

  // --- resolve the primary feature layer that drives the stats --------------
  var primary = await resolvePrimary(map);
  if (!primary) {
    document.getElementById("indicators").innerHTML =
      '<div class="muted">No feature layer found to summarise.</div>';
    if (chip) chip.textContent = "no data";
    return;
  }

  // Field introspection -> what the indicators / breakdown / list use.
  var fields = primary.fields || [];
  var oidField = primary.objectIdField;
  var valueFields = pickValueFields();
  var categoryField = pickCategory();
  var displayField = primary.displayField || categoryField || oidField;

  var nf = new Intl.NumberFormat();
  var cf = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });
  function fmt(n, compact) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    return (compact ? cf : nf).format(n);
  }

  var totalEl = null;
  buildIndicators();

  // Frame the data on first load (the webmap carries its own extent).
  if (!cfg.webmapId && primary.fullExtent) {
    try { await view.goTo(primary.fullExtent); } catch (e) {}
  }

  // Recompute whenever the view settles, and once now.
  reactiveUtils.watch(function () { return view.stationary; }, function (s) { if (s) refresh(); });
  refresh();

  // =========================================================================
  //  indicators
  // =========================================================================
  function buildIndicators() {
    var box = document.getElementById("indicators");
    box.innerHTML = "";
    totalEl = stat(box, "number", "Total features");
    valueFields.forEach(function (f) { f.el = stat(box, "graph-bar", "Sum · " + f.alias); });
    if (!valueFields.length) {
      var note = document.createElement("div");
      note.className = "muted";
      note.textContent = "No numeric fields to total.";
      box.appendChild(note);
    }
  }

  function stat(box, icon, label) {
    var card = document.createElement("calcite-card");
    var wrap = document.createElement("div"); wrap.className = "stat";
    var ic = document.createElement("calcite-icon"); ic.icon = icon; ic.scale = "l";
    var col = document.createElement("div");
    var v = document.createElement("div"); v.className = "stat-value"; v.textContent = "—";
    var l = document.createElement("div"); l.className = "stat-label"; l.textContent = label;
    col.appendChild(v); col.appendChild(l);
    wrap.appendChild(ic); wrap.appendChild(col);
    card.appendChild(wrap); box.appendChild(card);
    return v;
  }

  // =========================================================================
  //  refresh (count + sums + breakdown + list), scoped to the current extent
  // =========================================================================
  async function refresh() {
    if (!primary) return;
    var geom = view.extent;
    try {
      var count = await primary.queryFeatureCount({ geometry: geom, spatialRelationship: "intersects" });
      totalEl.textContent = fmt(count);
      if (chip) chip.textContent = fmt(count) + " in view";

      if (valueFields.length) {
        var outStats = valueFields.map(function (f, i) {
          return { statisticType: "sum", onStatisticField: f.name, outStatisticFieldName: "s" + i };
        });
        var res = await primary.queryFeatures({
          geometry: geom, spatialRelationship: "intersects",
          outStatistics: outStats, returnGeometry: false,
        });
        var a = (res.features[0] || { attributes: {} }).attributes;
        valueFields.forEach(function (f, i) { f.el.textContent = fmt(a["s" + i], true); });
      }
    } catch (e) { /* keep last values */ }

    refreshBreakdown(geom);
    refreshList(geom);
  }

  async function refreshBreakdown(geom) {
    var box = document.getElementById("breakdown");
    if (!categoryField) { box.innerHTML = '<div class="muted">No category field.</div>'; return; }
    try {
      var res = await primary.queryFeatures({
        geometry: geom, spatialRelationship: "intersects",
        groupByFieldsForStatistics: [categoryField],
        outStatistics: [{ statisticType: "count", onStatisticField: oidField, outStatisticFieldName: "cnt" }],
        orderByFields: ["cnt DESC"], returnGeometry: false, num: 8,
      });
      var rows = res.features.map(function (f) {
        var v = f.attributes[categoryField];
        return { name: (v === null || v === undefined || v === "") ? "(blank)" : String(v), count: f.attributes.cnt };
      });
      var max = rows.reduce(function (m, r) { return Math.max(m, r.count); }, 0) || 1;
      box.innerHTML = rows.length ? rows.map(function (r) {
        return '<div class="bar-row"><span class="bar-name" title="' + esc(r.name) + '">' + esc(r.name) +
          '</span><span class="bar-count">' + fmt(r.count) + '</span>' +
          '<span class="bar-track"><span class="bar-fill" style="width:' + (100 * r.count / max) + '%"></span></span></div>';
      }).join("") : '<div class="muted">Nothing in view.</div>';
    } catch (e) {
      box.innerHTML = '<div class="muted">Breakdown unavailable for this layer.</div>';
    }
  }

  async function refreshList(geom) {
    var list = document.getElementById("featList");
    try {
      var outFields = [oidField, displayField].concat(valueFields.map(function (f) { return f.name; }))
        .filter(function (v, i, arr) { return v && arr.indexOf(v) === i; });
      var res = await primary.queryFeatures({
        geometry: geom, spatialRelationship: "intersects",
        outFields: outFields, returnGeometry: true, num: 25,
        orderByFields: displayField ? [displayField + " ASC"] : null,
      });
      list.innerHTML = "";
      res.features.forEach(function (feat) {
        var item = document.createElement("calcite-list-item");
        var lbl = displayField ? feat.attributes[displayField] : null;
        item.label = (lbl === null || lbl === undefined || lbl === "")
          ? ("Feature " + feat.attributes[oidField]) : String(lbl);
        if (valueFields.length) {
          item.description = valueFields[0].alias + ": " + fmt(feat.attributes[valueFields[0].name]);
        }
        item.addEventListener("calciteListItemSelect", function () { flyTo(feat); });
        list.appendChild(item);
      });
    } catch (e) { /* ignore */ }
  }

  // =========================================================================
  //  fly + highlight + popup for a clicked feature
  // =========================================================================
  var _lv = null, _hl = null;
  async function flyTo(feat) {
    var target = feat.geometry;
    if (target && target.extent) { try { target = target.extent.clone().expand(1.6); } catch (e) {} }
    try { await view.goTo(target); } catch (e) {}
    try {
      if (!_lv) _lv = await view.whenLayerView(primary);
      if (_hl) _hl.remove();
      _hl = _lv.highlight(feat);
    } catch (e) {}
    try { view.openPopup({ features: [feat] }); } catch (e) {}
  }

  // =========================================================================
  //  helpers
  // =========================================================================
  async function resolvePrimary(map) {
    await map.when();
    var pick = function () { return map.allLayers.find(function (l) { return l.type === "feature"; }); };
    var layer = pick();
    if (!layer) {
      try { await reactiveUtils.whenOnce(function () { return pick(); }); layer = pick(); } catch (e) {}
    }
    if (layer) { try { await layer.load(); } catch (e) {} }
    return layer || null;
  }

  function pickValueFields() {
    if (cfg.valueFields && cfg.valueFields.length) {
      return cfg.valueFields.map(byName).filter(Boolean).map(toVF);
    }
    var picked = [];
    fields.forEach(function (f) {
      if (picked.length >= 3) return;
      if (NUMERIC[f.type] && f.name !== oidField && !/objectid|fid|shape|_id$/i.test(f.name)) picked.push(toVF(f));
    });
    return picked;
  }

  function pickCategory() {
    if (cfg.categoryField) return cfg.categoryField;
    var f = fields.find(function (fld) {
      return fld.type === "string" && !/url|guid|globalid|notes|desc|comment|address/i.test(fld.name);
    });
    return f ? f.name : null;
  }

  function byName(n) { return fields.find(function (f) { return f.name === n || f.alias === n; }); }
  function toVF(f) { return { name: f.name, alias: f.alias || f.name, el: null }; }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function viewReady(el) {
    if (el.ready) return Promise.resolve();
    return new Promise(function (resolve) {
      function h() { if (el.ready) { el.removeEventListener("arcgisViewReadyChange", h); resolve(); } }
      el.addEventListener("arcgisViewReadyChange", h);
    });
  }
})();
