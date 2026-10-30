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
  const btnFly = document.getElementById("btn-fly");
  const yardageHud = document.getElementById("yardage-hud");
  const yhHole = document.getElementById("yh-hole");
  const yhYards = document.getElementById("yh-yards");
  const yhMeta = document.getElementById("yh-meta");
  const scoreHint = document.getElementById("score-hint");
  const scoreEntry = document.getElementById("score-entry");
  const scoreKicker = document.getElementById("score-kicker");
  const scoreHole = document.getElementById("score-hole");
  const scoreNext = document.getElementById("score-next");
  const scoreCollapse = document.getElementById("score-collapse");
  const scoreMinus = document.getElementById("score-minus");
  const scorePlus = document.getElementById("score-plus");
  const scoreInput = document.getElementById("score-input");
  const scoreMic = document.getElementById("score-mic");
  const scoreHeard = document.getElementById("score-heard");

  const SCORE_KEY = "ou-golf-scores-v1";
  const PLAY_KEY = "ou-golf-playing-v1";
  const COURSE_NAMES = { katke: "Katke-Cousins", sharf: "R&S Sharf" };

  const KATKE = "#3ecf7a";
  const SHARF = "#4ea1ff";
  const PATH = "#f0c14b";
  const M_TO_YD = 1.0936132983377078;

  const map = L.map(mapEl, {
    zoomControl: false,
    attributionControl: true,
    maxZoom: 19,
  }).setView([42.6665, -83.203], 15);

  L.control.zoom({ position: "bottomright" }).addTo(map);

  mapEl.addEventListener("pointerdown", () => {
    if (flying) flyPointer = true;
  });
  mapEl.addEventListener(
    "wheel",
    () => {
      if (flying) flyPointer = true;
    },
    { passive: true }
  );
  map.on("dragstart zoomstart", () => {
    if (!flying || !flyPointer) return;
    stopFlyover();
  });

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
  let holeButtons = { katke: {}, sharf: {} };
  let pars = { katke: {}, sharf: {} };
  let scores = loadScores();
  /** @type {Record<string, Record<number, {lat:number, lon:number, props:object}>>} */
  let greenTargets = { katke: {}, sharf: {} };
  let userMarker = null;
  let userWatch = null;
  let accuracyCircle = null;
  let activeHoleBtn = null;
  let selectedHole = null; // { course, hole }
  let playingCourse = loadPlayingCourse();
  let lastHole = { katke: null, sharf: null };
  let lastUser = null; // { lat, lon, accuracy }
  let aimLine = null;
  let greenMarker = null;
  let recognition = null;
  let listening = false;
  let scoreCollapsed = false;
  let flyToken = 0;
  let flyMarker = null;
  let flying = false;
  let flyPointer = false;
  let flySnap = null;

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

  function metersBetween(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const toRad = (d) => (d * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  function yardsBetween(lat1, lon1, lat2, lon2) {
    return metersBetween(lat1, lon1, lat2, lon2) * M_TO_YD;
  }

  function popupHole(p, liveYards) {
    const live =
      liveYards != null
        ? `<br/><strong>${liveYards} yd</strong> to green (GPS)`
        : "";
    const saved = scores[p.course] && scores[p.course][p.hole];
    const scoreLine = saved != null ? `<br/>Your score: ${saved}` : "";
    return `<strong>${p.courseName} · Hole ${p.hole}</strong><br/>Par ${
      p.par || "—"
    } · ${p.yards || "—"} yd (Black)${scoreLine}${live}`;
  }

  function liveYardsFor(props) {
    if (!lastUser || !props) return null;
    const t = greenTargets[props.course] && greenTargets[props.course][props.hole];
    if (!t) return null;
    return Math.round(yardsBetween(lastUser.lat, lastUser.lon, t.lat, t.lon));
  }

  function refreshHolePopup(course, hole) {
    const layer = holeIndex[course] && holeIndex[course][hole];
    const t = greenTargets[course] && greenTargets[course][hole];
    if (!layer || !t) return;
    const yds = liveYardsFor(t.props);
    layer.setPopupContent(popupHole(t.props, yds));
  }

  function updateYardageHud() {
    if (!selectedHole) {
      yardageHud.hidden = true;
      if (aimLine) {
        map.removeLayer(aimLine);
        aimLine = null;
      }
      if (greenMarker) {
        map.removeLayer(greenMarker);
        greenMarker = null;
      }
      return;
    }

    const { course, hole } = selectedHole;
    const t = greenTargets[course] && greenTargets[course][hole];
    if (!t) {
      yardageHud.hidden = true;
      return;
    }

    yardageHud.hidden = false;
    yhHole.textContent = `${t.props.courseName} · Hole ${hole}`;

    const scorecard = `Par ${t.props.par || "—"} · ${
      t.props.yards || "—"
    } yd Black (scorecard)`;

    if (!lastUser) {
      yhYards.textContent = "—";
      yhMeta.textContent = "Waiting for GPS… · " + scorecard;
      return;
    }

    const yds = Math.round(
      yardsBetween(lastUser.lat, lastUser.lon, t.lat, t.lon)
    );
    const accYd =
      lastUser.accuracy != null
        ? Math.round(lastUser.accuracy * M_TO_YD)
        : null;
    yhYards.textContent = String(yds);
    yhMeta.textContent =
      "to green from your GPS" +
      (accYd != null ? ` (±${accYd} yd)` : "") +
      " · " +
      scorecard;

    const from = [lastUser.lat, lastUser.lon];
    const to = [t.lat, t.lon];
    if (!aimLine) {
      aimLine = L.polyline([from, to], {
        color: "#ffffff",
        weight: 2,
        opacity: 0.85,
        dashArray: "6 8",
      }).addTo(map);
    } else {
      aimLine.setLatLngs([from, to]);
      if (!map.hasLayer(aimLine)) aimLine.addTo(map);
    }

    if (!greenMarker) {
      greenMarker = L.circleMarker(to, {
        radius: 7,
        color: "#fff",
        weight: 2,
        fillColor: "#111",
        fillOpacity: 0.95,
      }).addTo(map);
    } else {
      greenMarker.setLatLng(to);
      if (!map.hasLayer(greenMarker)) greenMarker.addTo(map);
    }

    refreshHolePopup(course, hole);
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
      btn.addEventListener("click", () => focusHole(course, n, btn));
      holeButtons[course][n] = btn;
      listEl.appendChild(btn);
      paintScore(course, n);
    }
    renderTotals(course);
  }

  function holeLatLngs(layer) {
    let pts = layer.getLatLngs ? layer.getLatLngs() : [];
    if (pts.length && Array.isArray(pts[0])) pts = pts[0];
    return pts.filter((p) => p && typeof p.lat === "number");
  }

  function resamplePath(latlngs, steps) {
    if (latlngs.length < 2) return latlngs.slice();
    const seg = [];
    let total = 0;
    for (let i = 1; i < latlngs.length; i += 1) {
      const d = map.distance(latlngs[i - 1], latlngs[i]);
      seg.push(d);
      total += d;
    }
    if (total < 1) return latlngs.slice();
    const out = [];
    for (let s = 0; s <= steps; s += 1) {
      let remain = (total * s) / steps;
      let i = 0;
      while (i < seg.length - 1 && remain > seg[i]) {
        remain -= seg[i];
        i += 1;
      }
      const frac = seg[i] ? Math.min(1, remain / seg[i]) : 0;
      const a = latlngs[i];
      const b = latlngs[i + 1] || a;
      out.push(L.latLng(a.lat + (b.lat - a.lat) * frac, a.lng + (b.lng - a.lng) * frac));
    }
    return out;
  }

  function pointAlong(samples, t) {
    const clamped = Math.max(0, Math.min(1, t));
    const idx = clamped * (samples.length - 1);
    const i = Math.min(samples.length - 2, Math.floor(idx));
    const frac = idx - i;
    const a = samples[i];
    const b = samples[i + 1];
    return L.latLng(a.lat + (b.lat - a.lat) * frac, a.lng + (b.lng - a.lng) * frac);
  }

  function bearingDeg(a, b) {
    if (map.distance(a, b) < 0.5) return null;
    const φ1 = (a.lat * Math.PI) / 180;
    const φ2 = (b.lat * Math.PI) / 180;
    const Δλ = ((b.lng - a.lng) * Math.PI) / 180;
    const y = Math.sin(Δλ) * Math.cos(φ2);
    const x =
      Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
    return (Math.atan2(y, x) * 180) / Math.PI + 360;
  }

  function updateFlyButton() {
    if (!btnFly) return;
    btnFly.hidden = !selectedHole;
    btnFly.textContent = flying ? "Stop" : "Fly over";
    btnFly.setAttribute("aria-pressed", flying ? "true" : "false");
    btnFly.setAttribute(
      "aria-label",
      flying ? "Stop the fly-over" : "Fly over this hole from tee to green"
    );
  }

  function restoreFlySnap() {
    if (flySnap == null) return;
    map.options.zoomSnap = flySnap;
    flySnap = null;
  }

  function stopFlyover() {
    flyToken += 1;
    flying = false;
    flyPointer = false;
    restoreFlySnap();
    if (flyMarker) {
      map.removeLayer(flyMarker);
      flyMarker = null;
    }
    updateFlyButton();
  }

  function flyOver() {
    if (!selectedHole) return;
    if (flying) {
      stopFlyover();
      return;
    }
    const layer = holeIndex[selectedHole.course][selectedHole.hole];
    const path = layer ? holeLatLngs(layer) : [];
    if (path.length < 2) return;
    const samples = resamplePath(path, 90);
    if (layer) layer.closePopup();
    const meters = map.distance(samples[0], samples[samples.length - 1]);
    const reduceMotion =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const closeZoom = Math.min(19, map.getMaxZoom() || 19);
    const startZoom = map.getZoom();
    const dive = reduceMotion ? 0 : 1600;
    const cruise = reduceMotion
      ? 0
      : Math.max(5200, Math.min(9000, meters * M_TO_YD * 14));
    const duration = Math.max(1, dive + cruise);
    if (flySnap == null) flySnap = map.options.zoomSnap;
    map.options.zoomSnap = 0;
    flying = true;
    flyPointer = false;
    const token = ++flyToken;
    updateFlyButton();
    flyMarker = L.marker(samples[0], {
      icon: L.divIcon({
        className: "fly-marker",
        html: '<div class="fly-chevron"></div>',
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      }),
      interactive: false,
      keyboard: false,
      zIndexOffset: 900,
    }).addTo(map);
    let lastBearing = 0;
    const started = performance.now();

    function frame(now) {
      if (token !== flyToken) return;
      const elapsed = now - started;
      let along = 1;
      let zoom = closeZoom;
      if (elapsed < dive) {
        const u = elapsed / dive;
        const eased = 1 - (1 - u) ** 3;
        along = 0;
        zoom = startZoom + (closeZoom - startZoom) * eased;
      } else if (cruise > 0) {
        const u = Math.min(1, (elapsed - dive) / cruise);
        along = u < 0.5 ? 2 * u * u : 1 - ((-2 * u + 2) ** 2) / 2;
        zoom = closeZoom;
      }
      const here = pointAlong(samples, along);
      const ahead = pointAlong(samples, Math.min(1, Math.max(along, 0.015) + 0.03));
      const brg = bearingDeg(here, ahead);
      if (brg != null) lastBearing = brg % 360;
      map.setView(here, zoom, { animate: false });
      if (flyMarker) {
        flyMarker.setLatLng(here);
        const chevron =
          flyMarker.getElement() && flyMarker.getElement().querySelector(".fly-chevron");
        if (chevron) chevron.style.transform = "rotate(" + lastBearing + "deg)";
      }
      if (elapsed < duration) {
        requestAnimationFrame(frame);
      } else {
        flying = false;
        flyPointer = false;
        restoreFlySnap();
        if (flyMarker) {
          map.removeLayer(flyMarker);
          flyMarker = null;
        }
        updateFlyButton();
      }
    }

    requestAnimationFrame(frame);
  }

  function focusHole(course, n, btn) {
    const layer = holeIndex[course][n];
    if (!layer) return;
    stopFlyover();
    stopListening();
    if (activeHoleBtn) activeHoleBtn.classList.remove("active");
    if (btn) {
      btn.classList.add("active");
      activeHoleBtn = btn;
    } else {
      const list = course === "katke" ? listKatke : listSharf;
      const match = list.querySelector(`.hole-btn:nth-child(${n})`);
      if (match) {
        match.classList.add("active");
        activeHoleBtn = match;
      }
    }
    selectedHole = { course, hole: n };
    lastHole[course] = n;
    setPlayingCourse(course);
    refreshHolePopup(course, n);
    map.fitBounds(layer.getBounds(), { padding: [40, 40], maxZoom: 17 });
    if (scoreCollapsed) layer.closePopup();
    else layer.openPopup();
    updateYardageHud();
    showScoreEntry();
    updateFlyButton();
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
    lastUser = { lat, lon, accuracy };
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
    updateYardageHud();
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
          "GPS: " +
            latitude.toFixed(5) +
            ", " +
            longitude.toFixed(5) +
            " (±" +
            Math.round(accuracy) +
            " m)",
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
    prepareMic();
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
      loadJSON("meta.json"),
      loadJSON("boundary.geojson"),
      loadJSON("fairways.geojson"),
      loadJSON("greens.geojson"),
      loadJSON("tees.geojson"),
      loadJSON("cartpaths.geojson"),
      loadJSON("holes.geojson"),
      loadJSON("hole_labels.geojson"),
      loadJSON("pins.geojson"),
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
        const coords = feature.geometry.coordinates;
        // OSM hole lines end at the green / pin end.
        const end = coords[coords.length - 1];
        greenTargets[p.course][p.hole] = {
          lon: end[0],
          lat: end[1],
          props: p,
        };
        if (p.par) pars[p.course][p.hole] = p.par;
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
    paintAllScores();
    setPlayingCourse(playingCourse);
    startGps(false);
  }

  function loadPlayingCourse() {
    try {
      const saved = localStorage.getItem(PLAY_KEY);
      if (saved === "sharf" || saved === "katke") return saved;
    } catch (err) {
      /* Private mode can block storage. */
    }
    return "katke";
  }

  function setPlayingCourse(course) {
    if (course !== "katke" && course !== "sharf") course = "katke";
    playingCourse = course;
    try {
      localStorage.setItem(PLAY_KEY, course);
    } catch (err) {
      /* The choice still applies for this visit. */
    }
    const katkePanel = document.getElementById("course-katke");
    const sharfPanel = document.getElementById("course-sharf");
    const panel = course === "katke" ? katkePanel : sharfPanel;
    panel.hidden = false;
    const head = panel.querySelector(".course-head");
    if (head && scoreEntry.parentElement !== panel) {
      head.insertAdjacentElement("afterend", scoreEntry);
    }
    katkePanel.hidden = course !== "katke";
    sharfPanel.hidden = course !== "sharf";
    document.getElementById("play-katke").setAttribute("aria-selected", course === "katke" ? "true" : "false");
    document.getElementById("play-sharf").setAttribute("aria-selected", course === "sharf" ? "true" : "false");
  }

  function showPlayingCourse(course) {
    const remembered = lastHole[course];
    if (remembered && holeIndex[course] && holeIndex[course][remembered]) {
      focusHole(course, remembered);
      return;
    }
    stopFlyover();
    stopListening();
    setPlayingCourse(course);
    if (selectedHole && selectedHole.course !== course) {
      if (activeHoleBtn) activeHoleBtn.classList.remove("active");
      activeHoleBtn = null;
      selectedHole = null;
      updateYardageHud();
      updateFlyButton();
    }
    showScoreEntry();
    const holes = Object.values((holeIndex[course]) || {});
    if (holes.length) {
      map.fitBounds(L.featureGroup(holes).getBounds(), { padding: [30, 30] });
    }
  }

  function loadScores() {
    try {
      const raw = JSON.parse(localStorage.getItem(SCORE_KEY) || "{}");
      return { katke: sanitizeCourse(raw.katke), sharf: sanitizeCourse(raw.sharf) };
    } catch (err) {
      return { katke: {}, sharf: {} };
    }
  }

  function sanitizeCourse(raw) {
    const out = {};
    if (!raw || typeof raw !== "object") return out;
    for (let n = 1; n <= 18; n += 1) {
      const value = OUScore.clampStrokes(raw[n] != null ? raw[n] : raw[String(n)]);
      if (value != null) out[n] = value;
    }
    return out;
  }

  function saveScores() {
    try {
      localStorage.setItem(SCORE_KEY, JSON.stringify(scores));
    } catch (err) {
      /* Private mode can block storage; the card still works for this visit. */
    }
  }

  function paintScore(course, hole) {
    const btn = holeButtons[course][hole];
    if (!btn) return;
    const value = scores[course][hole];
    btn.replaceChildren();
    const num = document.createElement("span");
    num.className = "hb-n";
    num.textContent = String(hole);
    const mark = document.createElement("span");
    mark.className = "hb-s";
    mark.textContent = value == null ? "" : String(value);
    btn.append(num, mark);
    btn.classList.toggle("scored", value != null);
    btn.setAttribute(
      "aria-label",
      value == null ? "Hole " + hole : "Hole " + hole + ", " + value + " strokes"
    );
  }

  function paintAllScores() {
    ["katke", "sharf"].forEach((course) => {
      for (let n = 1; n <= 18; n += 1) paintScore(course, n);
      renderTotals(course);
    });
  }

  function renderTotals(course) {
    const el = document.getElementById("totals-" + course);
    if (!el) return;
    el.replaceChildren();
    const rows = [
      ["Out", OUScore.nineSummary(scores[course], pars[course], 1, 9), false],
      ["In", OUScore.nineSummary(scores[course], pars[course], 10, 18), false],
      ["18 holes", OUScore.nineSummary(scores[course], pars[course], 1, 18), true],
    ];
    rows.forEach((row) => {
      const cell = document.createElement("div");
      if (row[2]) cell.className = "round-total";
      const label = document.createElement("span");
      label.textContent = row[0];
      const strong = document.createElement("strong");
      strong.textContent = OUScore.formatStrokes(row[1]);
      cell.append(label, strong);
      el.appendChild(cell);
    });
  }

  function showScoreEntry() {
    if (!selectedHole || selectedHole.course !== playingCourse) {
      scoreEntry.hidden = true;
      scoreHint.hidden = false;
      return;
    }
    const course = selectedHole.course;
    const hole = selectedHole.hole;
    const par = pars[course][hole];
    const saved = scores[course][hole];
    scoreEntry.hidden = false;
    scoreHint.hidden = true;
    scoreKicker.textContent = COURSE_NAMES[course] || course;
    scoreHole.textContent =
      "Hole " +
      hole +
      (par ? " · Par " + par : "") +
      (scoreCollapsed && saved != null ? " · " + saved : "");
    scoreInput.value = saved == null ? "" : String(saved);
    scoreNext.disabled = hole >= 18;
    scoreNext.textContent = hole >= 18 ? "Last hole" : "Next hole";
    scoreHeard.textContent =
      saved == null
        ? "Say the strokes, or type them."
        : saved + (saved === 1 ? " stroke saved." : " strokes saved.");
    scoreEntry.classList.toggle("is-collapsed", scoreCollapsed);
    scoreCollapse.textContent = scoreCollapsed ? "Score" : "Hide";
    scoreCollapse.setAttribute("aria-expanded", scoreCollapsed ? "false" : "true");
    if (!scoreCollapsed) scoreEntry.scrollIntoView({ block: "nearest" });
  }

  function setScoreCollapsed(collapsed) {
    scoreCollapsed = collapsed;
    if (collapsed) stopListening();
    if (selectedHole) {
      const layer = holeIndex[selectedHole.course][selectedHole.hole];
      if (layer && collapsed) layer.closePopup();
    }
    showScoreEntry();
  }

  function setScore(course, hole, strokes) {
    if (strokes == null) delete scores[course][hole];
    else scores[course][hole] = strokes;
    saveScores();
    paintScore(course, hole);
    renderTotals(course);
    if (selectedHole && selectedHole.course === course && selectedHole.hole === hole) {
      const shown = strokes == null ? "" : String(strokes);
      if (scoreInput.value !== shown) scoreInput.value = shown;
    }
    refreshHolePopup(course, hole);
  }

  function commitTypedScore() {
    if (!selectedHole) return;
    const raw = scoreInput.value.trim();
    if (raw === "") {
      setScore(selectedHole.course, selectedHole.hole, null);
      scoreHeard.textContent = "Score cleared. Say or type the strokes.";
      return;
    }
    const strokes = OUScore.clampStrokes(raw);
    if (strokes == null) {
      const saved = scores[selectedHole.course][selectedHole.hole];
      scoreInput.value = saved == null ? "" : String(saved);
      scoreHeard.textContent = "Enter 1 to 20 strokes.";
      return;
    }
    setScore(selectedHole.course, selectedHole.hole, strokes);
    scoreHeard.textContent =
      strokes + (strokes === 1 ? " stroke saved." : " strokes saved.");
  }

  function bumpScore(delta) {
    if (!selectedHole) return;
    const course = selectedHole.course;
    const hole = selectedHole.hole;
    const current = scores[course][hole];
    let next;
    if (current == null) {
      if (delta < 0) return;
      next = pars[course][hole] || 4;
    } else {
      next = current + delta;
    }
    next = OUScore.clampStrokes(next);
    if (next == null) return;
    setScore(course, hole, next);
    scoreHeard.textContent =
      next + (next === 1 ? " stroke saved." : " strokes saved.");
  }

  function clearCourse(course) {
    const name = COURSE_NAMES[course] || course;
    if (!window.confirm("Clear all " + name + " scores?")) return;
    scores[course] = {};
    saveScores();
    for (let n = 1; n <= 18; n += 1) {
      paintScore(course, n);
      refreshHolePopup(course, n);
    }
    renderTotals(course);
    if (selectedHole && selectedHole.course === course) showScoreEntry();
  }

  function speechCtor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function prepareMic() {
    if (speechCtor()) return;
    scoreMic.disabled = true;
    scoreMic.textContent = "No mic";
    scoreMic.title = "This browser cannot hear a score. Type the strokes.";
  }

  function stopListening() {
    if (!recognition) return;
    try {
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      recognition.abort();
    } catch (err) {
      /* already stopped */
    }
    listening = false;
    scoreMic.classList.remove("listening");
    scoreMic.setAttribute("aria-pressed", "false");
    if (!scoreMic.disabled) scoreMic.textContent = "Say score";
  }

  function listenForScore() {
    const Ctor = speechCtor();
    if (!Ctor || !selectedHole) return;
    if (listening) {
      stopListening();
      scoreHeard.textContent = "Stopped. Say the strokes, or type them.";
      return;
    }
    const course = selectedHole.course;
    const hole = selectedHole.hole;
    const par = pars[course][hole];
    recognition = new Ctor();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.maxAlternatives = 4;
    recognition.continuous = false;

    recognition.onstart = () => {
      listening = true;
      scoreMic.classList.add("listening");
      scoreMic.setAttribute("aria-pressed", "true");
      scoreMic.textContent = "Listening";
      scoreHeard.textContent = "Listening… say the strokes, like 5, or bogey.";
    };

    recognition.onresult = (event) => {
      let interim = "";
      let finalText = "";
      const finals = [];
      for (let i = 0; i < event.results.length; i += 1) {
        const piece = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalText += piece;
          for (let a = 0; a < event.results[i].length; a += 1) {
            finals.push(event.results[i][a].transcript);
          }
        } else {
          interim += piece;
        }
      }
      if (!finalText.trim()) {
        scoreHeard.textContent = interim.trim()
          ? "Hearing “" + interim.trim() + "”…"
          : "Listening…";
        return;
      }
      const heard = (finals[0] || finalText).trim();
      let strokes = null;
      const candidates = finals.length ? finals : [finalText];
      for (let i = 0; i < candidates.length; i += 1) {
        strokes = OUScore.parseSpokenScore(candidates[i], par);
        if (strokes != null) break;
      }
      if (strokes == null) {
        scoreHeard.textContent = heard
          ? "Heard “" + heard + "”. Say a number of strokes, or type it."
          : "Didn't catch that. Type the strokes.";
        return;
      }
      if (!selectedHole || selectedHole.course !== course || selectedHole.hole !== hole) return;
      setScore(course, hole, strokes);
      scoreHeard.textContent = "Heard “" + heard + "”. Saved " + strokes + ".";
    };

    recognition.onerror = (event) => {
      if (!event || event.error === "aborted") return;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        scoreHeard.textContent =
          "Microphone is blocked. Type the strokes, or allow the mic for this site.";
      } else if (event.error === "no-speech") {
        scoreHeard.textContent = "Didn't hear a score. Try again, or type the strokes.";
      } else {
        scoreHeard.textContent = "Couldn't use the microphone. Type the strokes.";
      }
    };

    recognition.onend = () => {
      listening = false;
      scoreMic.classList.remove("listening");
      scoreMic.setAttribute("aria-pressed", "false");
      if (!scoreMic.disabled) scoreMic.textContent = "Say score";
    };

    try {
      recognition.start();
    } catch (err) {
      listening = false;
      scoreHeard.textContent = "Couldn't start listening. Type the strokes.";
    }
  }

  togKatke.addEventListener("change", applyToggles);
  togSharf.addEventListener("change", applyToggles);
  togPaths.addEventListener("change", applyToggles);
  togFairways.addEventListener("change", applyToggles);
  document.getElementById("play-katke").addEventListener("click", () => showPlayingCourse("katke"));
  document.getElementById("play-sharf").addEventListener("click", () => showPlayingCourse("sharf"));
  btnLocate.addEventListener("click", () => startGps(true));
  btnFly.addEventListener("click", flyOver);
  scoreMinus.addEventListener("click", () => bumpScore(-1));
  scorePlus.addEventListener("click", () => bumpScore(1));
  scoreInput.addEventListener("input", () => {
    if (!selectedHole) return;
    const raw = scoreInput.value.trim();
    if (raw === "") {
      setScore(selectedHole.course, selectedHole.hole, null);
      return;
    }
    const strokes = OUScore.clampStrokes(raw);
    if (strokes == null) return;
    setScore(selectedHole.course, selectedHole.hole, strokes);
    scoreHeard.textContent =
      strokes + (strokes === 1 ? " stroke saved." : " strokes saved.");
  });
  scoreInput.addEventListener("blur", commitTypedScore);
  scoreMic.addEventListener("click", listenForScore);
  scoreCollapse.addEventListener("click", () => setScoreCollapsed(!scoreCollapsed));
  scoreNext.addEventListener("click", () => {
    if (!selectedHole || selectedHole.hole >= 18) return;
    focusHole(selectedHole.course, selectedHole.hole + 1);
  });
  document.getElementById("clear-katke").addEventListener("click", () => clearCourse("katke"));
  document.getElementById("clear-sharf").addEventListener("click", () => clearCourse("sharf"));

  setPlayingCourse(playingCourse);

  init().catch((err) => {
    console.error(err);
    setGpsStatus("Could not load course map data.", "err");
  });
})();
