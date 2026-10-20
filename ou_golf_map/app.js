(() => {
  const mapEl = document.getElementById("map");
  const gpsStatus = document.getElementById("gps-status");
  const btnLocate = document.getElementById("btn-locate");
  const listKatke = document.getElementById("list-katke");
  const listSharf = document.getElementById("list-sharf");
  const togKatke = document.getElementById("tog-katke");
  const togSharf = document.getElementById("tog-sharf");
  const togPaths = document.getElementById("tog-paths");
  const togFairways = document.getElementById("tog-fairways");

  const KATKE = "#3ecf7a";
  const SHARF = "#4ea1ff";
  const PATH = "#f0c14b";

  const map = L.map(mapEl, {
    zoomControl: false,
    attributionControl: true,
  }).setView([42.6665, -83.203], 15);

  L.control.zoom({ position: "bottomright" }).addTo(map);

  L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 19,
      attribution: "Tiles © Esri",
    }
  ).addTo(map);

  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
    {
      maxZoom: 19,
      opacity: 0.7,
      attribution: "© OSM © CARTO",
    }
  ).addTo(map);

  const layers = {
    boundary: L.layerGroup().addTo(map),
    fairways: L.layerGroup().addTo(map),
    greens: L.layerGroup().addTo(map),
    tees: L.layerGroup().addTo(map),
    paths: L.layerGroup().addTo(map),
    holesKatke: L.layerGroup().addTo(map),
    holesSharf: L.layerGroup().addTo(map),
    labelsKatke: L.layerGroup().addTo(map),
    labelsSharf: L.layerGroup().addTo(map),
    pins: L.layerGroup().addTo(map),
  };

  let holeIndex = { katke: {}, sharf: {} };
  let userMarker = null;
  let userWatch = null;
  let accuracyCircle = null;
  let activeHoleBtn = null;

  function holeIcon(course, num) {
    return L.divIcon({
      className: "",
      html: `<div class="hole-label ${course}">${num}</div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
  }

  async function loadJSON(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error("Failed to load " + path);
    return res.json();
  }

  function popupHole(p) {
    return `<strong>${p.courseName} · Hole ${p.hole}</strong><br/>Par ${p.par || "—"} · ${p.yards || "—"} yd (Black)`;
  }

  function addPolygonLayer(fc, group, style) {
    L.geoJSON(fc, {
      style,
      onEachFeature(feature, layer) {
        const k = feature.properties && feature.properties.kind;
        if (k) layer.bindPopup(k.replace("_", " "));
      },
    }).addTo(group);
  }

  function buildHoleButtons(course, listEl) {
    listEl.innerHTML = "";
    for (let n = 1; n <= 18; n += 1) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "hole-btn " + course;
      btn.textContent = String(n);
      btn.addEventListener("click", () => focusHole(course, n, btn));
      listEl.appendChild(btn);
    }
  }

  function focusHole(course, n, btn) {
    const layer = holeIndex[course][n];
    if (!layer) return;
    if (activeHoleBtn) activeHoleBtn.classList.remove("active");
    if (btn) {
      btn.classList.add("active");
      activeHoleBtn = btn;
    }
    map.fitBounds(layer.getBounds(), { padding: [40, 40], maxZoom: 17 });
    layer.openPopup();
  }

  function applyToggles() {
    const showK = togKatke.checked;
    const showS = togSharf.checked;
    const showP = togPaths.checked;
    const showF = togFairways.checked;

    setLayer(layers.holesKatke, showK);
    setLayer(layers.labelsKatke, showK);
    setLayer(layers.holesSharf, showS);
    setLayer(layers.labelsSharf, showS);
    setLayer(layers.paths, showP);
    setLayer(layers.fairways, showF);
    setLayer(layers.greens, showF);
    setLayer(layers.tees, showF);
    setLayer(layers.pins, showF);
  }

  function setLayer(group, on) {
    if (on) {
      if (!map.hasLayer(group)) group.addTo(map);
    } else if (map.hasLayer(group)) {
      map.removeLayer(group);
    }
  }

  function setGpsStatus(msg, kind) {
    gpsStatus.textContent = msg;
    gpsStatus.className = "status" + (kind ? " " + kind : "");
  }

  function upsertUser(lat, lon, accuracy) {
    const ll = [lat, lon];
    if (!userMarker) {
      userMarker = L.marker(ll, {
        icon: L.divIcon({
          className: "",
          html: '<div class="user-dot"></div>',
          iconSize: [16, 16],
          iconAnchor: [8, 8],
        }),
        zIndexOffset: 1000,
      }).addTo(map);
      accuracyCircle = L.circle(ll, {
        radius: accuracy || 20,
        color: "#ff5a3c",
        weight: 1,
        fillColor: "#ff5a3c",
        fillOpacity: 0.12,
      }).addTo(map);
    } else {
      userMarker.setLatLng(ll);
      accuracyCircle.setLatLng(ll);
      accuracyCircle.setRadius(accuracy || 20);
    }
  }

  function startGps(centerOnFix) {
    if (!navigator.geolocation) {
      setGpsStatus("GPS not available on this device.", "err");
      return;
    }
    setGpsStatus("GPS: locating…");
    if (userWatch != null) navigator.geolocation.clearWatch(userWatch);

    userWatch = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        upsertUser(latitude, longitude, accuracy);
        setGpsStatus(
          "GPS: " + latitude.toFixed(5) + ", " + longitude.toFixed(5) +
            " (±" + Math.round(accuracy) + " m)",
          "ok"
        );
        if (centerOnFix) {
          map.setView([latitude, longitude], Math.max(map.getZoom(), 17));
          centerOnFix = false;
        }
      },
      (err) => {
        setGpsStatus("GPS error: " + (err.message || "permission denied"), "err");
      },
      { enableHighAccuracy: true, maximumAge: 3000, timeout: 15000 }
    );
  }

  async function init() {
    buildHoleButtons("katke", listKatke);
    buildHoleButtons("sharf", listSharf);

    const [
      meta,
      boundary,
      fairways,
      greens,
      tees,
      cartpaths,
      holes,
      labels,
      pins,
    ] = await Promise.all([
      loadJSON("data/meta.json"),
      loadJSON("data/boundary.geojson"),
      loadJSON("data/fairways.geojson"),
      loadJSON("data/greens.geojson"),
      loadJSON("data/tees.geojson"),
      loadJSON("data/cartpaths.geojson"),
      loadJSON("data/holes.geojson"),
      loadJSON("data/hole_labels.geojson"),
      loadJSON("data/pins.geojson"),
    ]);

    document.getElementById("attrib").textContent =
      meta.attribution + " · Yardages from oakland.edu/golf · Imagery © Esri";

    L.geoJSON(boundary, {
      style: {
        color: "#ffffff",
        weight: 1.5,
        opacity: 0.55,
        fillColor: "#ffffff",
        fillOpacity: 0.03,
      },
    }).addTo(layers.boundary);

    addPolygonLayer(fairways, layers.fairways, {
      color: "#7CFFB2",
      weight: 0.5,
      fillColor: "#2f8f55",
      fillOpacity: 0.28,
    });
    addPolygonLayer(greens, layers.greens, {
      color: "#b8ff6a",
      weight: 1,
      fillColor: "#78d63d",
      fillOpacity: 0.45,
    });
    addPolygonLayer(tees, layers.tees, {
      color: "#d9c27a",
      weight: 0.5,
      fillColor: "#c7a85a",
      fillOpacity: 0.35,
    });

    L.geoJSON(cartpaths, {
      style(feature) {
        const maint = feature.properties.kind === "maintenance";
        return {
          color: PATH,
          weight: maint ? 2 : 2.5,
          opacity: 0.9,
          dashArray: maint ? "4 6" : null,
        };
      },
      onEachFeature(feature, layer) {
        layer.bindPopup(feature.properties.name || "Path");
      },
    }).addTo(layers.paths);

    L.geoJSON(holes, {
      style(feature) {
        const course = feature.properties.course;
        return {
          color: course === "katke" ? KATKE : SHARF,
          weight: 3.5,
          opacity: 0.95,
        };
      },
      onEachFeature(feature, layer) {
        const p = feature.properties;
        layer.bindPopup(popupHole(p));
        holeIndex[p.course][p.hole] = layer;
        if (p.course === "katke") layer.addTo(layers.holesKatke);
        else layer.addTo(layers.holesSharf);
      },
    });

    L.geoJSON(labels, {
      pointToLayer(feature, latlng) {
        const p = feature.properties;
        return L.marker(latlng, {
          icon: holeIcon(p.course, p.shortLabel),
          interactive: true,
        });
      },
      onEachFeature(feature, layer) {
        const p = feature.properties;
        layer.bindPopup(popupHole(p));
        layer.on("click", () => focusHole(p.course, p.hole));
        if (p.course === "katke") layer.addTo(layers.labelsKatke);
        else layer.addTo(layers.labelsSharf);
      },
    });

    L.geoJSON(pins, {
      pointToLayer(feature, latlng) {
        return L.circleMarker(latlng, {
          radius: 3,
          color: "#fff",
          weight: 1,
          fillColor: "#111",
          fillOpacity: 0.9,
        });
      },
    }).addTo(layers.pins);

    if (meta.clubhouse) {
      L.marker([meta.clubhouse.lat, meta.clubhouse.lon])
        .addTo(map)
        .bindPopup(
          `<strong>${meta.clubhouse.name}</strong><br/>${meta.clubhouse.address}`
        );
    }

    const allHoleLayers = [
      ...Object.values(holeIndex.katke),
      ...Object.values(holeIndex.sharf),
    ];
    if (allHoleLayers.length) {
      const group = L.featureGroup(allHoleLayers);
      map.fitBounds(group.getBounds(), { padding: [30, 30] });
    }

    applyToggles();
    startGps(false);
  }

  togKatke.addEventListener("change", applyToggles);
  togSharf.addEventListener("change", applyToggles);
  togPaths.addEventListener("change", applyToggles);
  togFairways.addEventListener("change", applyToggles);
  btnLocate.addEventListener("click", () => startGps(true));

  init().catch((err) => {
    console.error(err);
    setGpsStatus("Could not load course map data.", "err");
  });
})();
