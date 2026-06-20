/* ArcGIS Maps SDK for JavaScript 5.0 — component-driven app logic.
 *
 * The map and its widgets are declared as <arcgis-*> web components in
 * index.html. This file only wires in the runtime configuration from
 * window.APP_CONFIG (see config.js):
 *   - sets the portal, then the map source (saved Web Map id OR basemap),
 *   - adds hosted feature layers when no Web Map id is given,
 *   - prunes the declared widgets down to the configured set.
 *
 * Core API classes are loaded from the CDN bundle via the global $arcgis.import()
 * — the 5.0 replacement for the old AMD require([...]).
 */
(async function () {
  "use strict";

  var cfg = window.APP_CONFIG || {};

  // Map the generator's widget names to the element ids declared in index.html.
  var WIDGET_IDS = {
    home: "w-home",
    search: "w-search",
    legend: "w-legend",
    layerList: "w-layerlist",
    basemapGallery: "w-basemap",
  };

  // Wait until the SDK bundle has registered the components ($arcgis is ready too).
  await customElements.whenDefined("arcgis-map");

  var mapEl = document.querySelector("arcgis-map");
  if (!mapEl) return;

  // The description goes on the Calcite navigation logo (the heading/title itself
  // is baked into the template at generation time).
  var logo = document.getElementById("appLogo");
  if (logo && cfg.description) logo.description = cfg.description;

  // Keep only the widgets that were configured; remove the rest from the DOM.
  var enabled = {};
  (cfg.widgets || []).forEach(function (w) { enabled[w] = true; });
  Object.keys(WIDGET_IDS).forEach(function (name) {
    if (!enabled[name]) {
      var el = document.getElementById(WIDGET_IDS[name]);
      if (el) el.remove();
    }
  });

  // Point the SDK at the configured portal BEFORE any item loads (AGOL by
  // default; an Enterprise portal URL works once it's in the config).
  if (cfg.portalUrl) {
    try {
      var imported = await $arcgis.import(["@arcgis/core/config.js"]);
      imported[0].portalUrl = cfg.portalUrl;
    } catch (e) { /* non-fatal: default portal still works */ }
  }

  if (cfg.webmapId) {
    // --- Path A: load a saved Web Map (keeps its symbology, labeling, popups) -
    mapEl.itemId = cfg.webmapId;
  } else {
    // --- Path B: build a map from hosted feature layers on a basemap ----------
    mapEl.basemap = cfg.basemap || "topo-vector";
    mapEl.center = [0, 20];
    mapEl.zoom = 3;

    var ids = cfg.layerItemIds || [];
    if (ids.length) {
      var mods = await $arcgis.import(["@arcgis/core/layers/FeatureLayer.js"]);
      var FeatureLayer = mods[0];
      await viewReady(mapEl);
      ids.forEach(function (id) {
        mapEl.map.add(new FeatureLayer({ portalItem: { id: id } }));
      });
    }
  }

  // Resolve once the map component's view is ready (so mapEl.map exists).
  function viewReady(el) {
    if (el.ready) return Promise.resolve();
    return new Promise(function (resolve) {
      function handler() {
        if (el.ready) {
          el.removeEventListener("arcgisViewReadyChange", handler);
          resolve();
        }
      }
      el.addEventListener("arcgisViewReadyChange", handler);
    });
  }
})();
