(() => {
  const mapEl = document.getElementById("map");
  const gpsStatus = document.getElementById("gps-status");
  const btnLocate = document.getElementById("btn-locate");
  const listHoles = document.getElementById("list-wyndgate");
  const togHoles = document.getElementById("tog-holes");
  const togPaths = document.getElementById("tog-paths");
  const togFairways = document.getElementById("tog-fairways");
  const imagerySelect = document.getElementById("imagery-select");
  const btnFly = document.getElementById("btn-fly");
  const btnVideo = document.getElementById("btn-video");
  const videoModal = document.getElementById("video-modal");
  const videoTitle = document.getElementById("video-title");
  const videoClose = document.getElementById("video-close");
  const holeVideo = document.getElementById("hole-video");
  const btnReset = document.getElementById("btn-reset");
  const btnBreaks = document.getElementById("btn-breaks");
  const yardageHud = document.getElementById("yardage-hud");
  const yhHole = document.getElementById("yh-hole");
  const yhYards = document.getElementById("yh-yards");
  const yhFrontWrap = document.getElementById("yh-front-wrap");
  const yhBackWrap = document.getElementById("yh-back-wrap");
  const yhFront = document.getElementById("yh-front");
  const yhBack = document.getElementById("yh-back");
  const yhMeta = document.getElementById("yh-meta");
  const btnCenter = document.getElementById("btn-center");
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
  const scorePlays = document.getElementById("score-plays");
  const scoreRoll = document.getElementById("score-roll");

  const teeSelect = document.getElementById("tee-select");
  const hcpSelect = document.getElementById("hcp-select");
  const brandSub = document.getElementById("brand-sub");
  const cardNote = document.getElementById("card-note");

  const SCORE_KEY = "wyndgate-scores-v1";
  const TEE_KEY = "wyndgate-tee-v1";
  const HCP_KEY = "wyndgate-hcp-v1";
  const TEE_IDS = ["black", "blue", "silver", "silvergreen", "green", "blackm", "gold"];
  const COURSE = "wyndgate";
  const COURSE_NAMES = { wyndgate: "The Wyndgate" };
  let card = null;
  let teeId = loadTee();
  let hcpSet = loadHcp();

  const HOLE = "#3ecf7a";
  const PATH = "#f0c14b";
  const M_TO_YD = 1.0936132983377078;

  const map = L.map(mapEl, {
    zoomControl: false,
    attributionControl: true,
    maxZoom: 21,
  }).setView([42.73513, -83.17693], 15);

  L.control.zoom({ position: "bottomright" }).addTo(map);
  const yardagePane = map.createPane("yardage");
  yardagePane.style.zIndex = 450;
  yardagePane.style.pointerEvents = "none";

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
  map.on("click", (e) => {
    if (!selectedHole || flying || ballMarker) return;
    const el = e.originalEvent && e.originalEvent.target;
    if (
      el &&
      el.closest &&
      el.closest(".leaflet-marker-icon, .leaflet-popup, .hole-label, .fly-btn, .leaflet-control")
    ) {
      return;
    }
    markTarget = e.latlng;
    updateYardageHud();
  });

  // Web-mercator constants for USGS NAIP exportImage tiles (no public XYZ CDN).
  const MERC_ORIGIN = 20037508.342789244;
  const MERC_RES0 = 156543.03392804097;

  const NaipTileLayer = L.TileLayer.extend({
    getTileUrl: function (coords) {
      const z = coords.z;
      const x = coords.x;
      const y = coords.y;
      const size = this.getTileSize().x;
      const res = MERC_RES0 / Math.pow(2, z);
      const xmin = x * size * res - MERC_ORIGIN;
      const ymin = MERC_ORIGIN - (y + 1) * size * res;
      const xmax = (x + 1) * size * res - MERC_ORIGIN;
      const ymax = MERC_ORIGIN - y * size * res;
      return (
        "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer/exportImage" +
        "?bbox=" +
        [xmin, ymin, xmax, ymax].join(",") +
        "&bboxSR=3857&imageSR=3857&size=" +
        size +
        "," +
        size +
        "&format=jpg&f=image"
      );
    },
  });

  // Paste a free public token from https://account.mapbox.com/access-tokens/
  // Leave empty until pasted — selecting Mapbox then shows a brief status note.
  const MAPBOX_ACCESS_TOKEN = "";

  const imageryLayers = {
    naip: new NaipTileLayer("", {
      maxZoom: 21,
      // NAIP is ~0.6–1 m; past ~18 Leaflet is mostly upscaling.
      maxNativeZoom: 18,
      attribution: "Imagery © USGS NAIP",
      crossOrigin: true,
    }),
    esri: L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 21,
        maxNativeZoom: 19,
        attribution: "Tiles © Esri",
      }
    ),
  };
  if (MAPBOX_ACCESS_TOKEN) {
    imageryLayers.mapbox = L.tileLayer(
      "https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.jpg?access_token=" +
        encodeURIComponent(MAPBOX_ACCESS_TOKEN),
      {
        maxZoom: 22,
        attribution: "© Mapbox © Maxar",
      }
    );
  }
  let activeImagery = "naip";
  imageryLayers.naip.addTo(map);

  // Basemaps API key (cb1_…), same as OU / Indianwood. A CARTO Developers JWT
  // in ?key= still returns watermarked tiles (etag wm-*).
  const CARTO_API_KEY =
    "cb1_5dhw_1_df8e4cfc1a9a6aed2d27b170";

  const labelsLayer = L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png?key=" +
      encodeURIComponent(CARTO_API_KEY),
    {
      maxZoom: 21,
      maxNativeZoom: 19,
      opacity: 0.7,
      attribution: "© OSM © CARTO",
    }
  ).addTo(map);

  function imageryCredit() {
    if (activeImagery === "naip") return "Imagery © USGS NAIP";
    if (activeImagery === "mapbox") return "Imagery © Mapbox © Maxar";
    return "Imagery © Esri";
  }

  function noteMapboxToken() {
    const el = document.getElementById("imagery-note");
    if (!el) return;
    el.hidden = false;
    el.textContent =
      "Paste a Mapbox token into MAPBOX_ACCESS_TOKEN in app.js (account.mapbox.com/access-tokens).";
    clearTimeout(noteMapboxToken._t);
    noteMapboxToken._t = setTimeout(() => {
      el.hidden = true;
      el.textContent = "";
    }, 6000);
  }

  function setImagery(kind) {
    if (kind === "mapbox" && !imageryLayers.mapbox) {
      if (imagerySelect) imagerySelect.value = activeImagery;
      noteMapboxToken();
      return;
    }
    const next = imageryLayers[kind] ? kind : "naip";
    if (next === activeImagery) return;
    map.removeLayer(imageryLayers[activeImagery]);
    imageryLayers[next].addTo(map);
    // Keep street labels above the satellite layer.
    if (map.hasLayer(labelsLayer)) labelsLayer.bringToFront();
    activeImagery = next;
    if (imagerySelect && imagerySelect.value !== next) imagerySelect.value = next;
    const foot = document.getElementById("attrib");
    if (foot && foot.dataset.base) {
      foot.textContent = foot.dataset.base + " · " + imageryCredit();
    } else if (foot) {
      foot.textContent = "Map data © OpenStreetMap · " + imageryCredit();
    }
  }

  const layers = {
    boundary: L.layerGroup().addTo(map),
    fairways: L.layerGroup().addTo(map),
    greens: L.layerGroup().addTo(map),
    tees: L.layerGroup().addTo(map),
    paths: L.layerGroup().addTo(map),
    holes: L.layerGroup().addTo(map),
    labels: L.layerGroup().addTo(map),
    pins: L.layerGroup().addTo(map),
  };

  let holeIndex = { wyndgate: {} };
  let holeButtons = { wyndgate: {} };
  let pars = { wyndgate: {} };
  let scores = loadScores();
  /** @type {Record<string, Record<number, {lat:number, lon:number, props:object}>>} */
  let greenTargets = { wyndgate: {} };
  let userMarker = null;
  let userWatch = null;
  let accuracyCircle = null;
  let activeHoleBtn = null;
  let selectedHole = null; // { course, hole }
  let markTarget = null; // a map tap, measured instead of the green
  let markMarker = null;
  let playingCourse = COURSE;
  let lastHole = { wyndgate: null };
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
    const facts = holeFacts(p.course, p.hole);
    const fallback = `Par ${p.par || "—"} · ${p.yards || "—"} yd (Black)`;
    const roll = rollPhrase(p.course, p.hole);
    const rollLine = roll ? `<br/>${roll}` : "";
    return `<strong>${p.courseName} · Hole ${p.hole}</strong><br/>${
      facts || fallback
    }${rollLine}${scoreLine}${live}`;
  }

  let greenSlopes = null;
  let greenGrids = null;
  let slopeLayer = null;
  let ballMarker = null;
  let pinMarker = null;
  let puttLine = null;
  let puttShade = null;
  let puttRead = "";

  function greenSlope(course, hole) {
    const book = greenSlopes && greenSlopes.greens && greenSlopes.greens[course];
    return book ? book[String(hole)] : null;
  }

  function rollPhrase(course, hole) {
    const info = greenSlope(course, hole);
    if (!info) return "";
    const fall = Number(info.fallFt);
    if (!isFinite(fall)) return "";
    if (fall < 0.5) return "Green is nearly level";
    const fallText = fall.toFixed(1).replace(/\.0$/, "") + " ft of fall";
    const target = greenTargets[course] && greenTargets[course][hole];
    let shot = null;
    if (target && target.teeLat != null) {
      const bearing = bearingDeg(
        { lat: target.teeLat, lng: target.teeLon },
        { lat: target.lat, lng: target.lon }
      );
      shot = bearing == null ? null : ((bearing % 360) + 360) % 360;
    }
    if (shot == null || info.downDeg == null) return "Green has " + fallText;
    const rel = ((info.downDeg - shot) % 360 + 360) % 360;
    const away = Math.cos((rel * Math.PI) / 180);
    const toRight = Math.sin((rel * Math.PI) / 180);
    const cross = Math.abs(toRight) >= 0.35;
    const side = toRight >= 0 ? "the right" : "the left";
    let how = "off to " + side;
    if (away >= 0.5) how = cross ? "away from you, off to " + side : "away from you";
    else if (away <= -0.5) how = cross ? "back toward you, off to " + side : "back toward you";
    return "Ball rolls " + how + " · " + fallText;
  }

  function showGreenBreak(course, hole) {
    if (slopeLayer) {
      map.removeLayer(slopeLayer);
      slopeLayer = null;
    }
    const info = greenSlope(course, hole);
    if (!info) {
      if (btnBreaks) btnBreaks.hidden = true;
      return;
    }
    slopeLayer = L.imageOverlay(
      info.image,
      [
        [info.south, info.west],
        [info.north, info.east],
      ],
      { opacity: 1, interactive: false }
    ).addTo(map);
    if (btnBreaks) {
      btnBreaks.hidden = false;
      btnBreaks.setAttribute("aria-pressed", "false");
    }
    clearPutt();
  }

  function clearGreenBreak() {
    if (slopeLayer) {
      map.removeLayer(slopeLayer);
      slopeLayer = null;
    }
    if (btnBreaks) btnBreaks.hidden = true;
    clearPuttMarkers();
  }

  function finishMapZoom() {
    if (!map._animatingZoom) return;
    map._animatingZoom = false;
    if (map._mapPane) L.DomUtil.removeClass(map._mapPane, "leaflet-zoom-anim");
  }

  function zoomGreenBreak() {
    if (!slopeLayer || !selectedHole) return;
    map.closePopup();
    if (btnBreaks) btnBreaks.setAttribute("aria-pressed", "true");
    setupPutt(selectedHole.course, selectedHole.hole);
    const frame = ballMarker
      ? L.latLngBounds([ballMarker.getLatLng(), pinMarker.getLatLng()]).pad(1.1)
      : slopeLayer.getBounds();
    // The hole view may still be zooming. Leaflet drops a new fitBounds until that animation ends.
    finishMapZoom();
    map.fitBounds(frame, { padding: [64, 64], maxZoom: 21, animate: false });
  }

  function gridFor(course, hole) {
    const raw = greenGrids && greenGrids.greens && greenGrids.greens[course] && greenGrids.greens[course][String(hole)];
    if (!raw) return null;
    if (!raw.dzdx) {
      const bytes = Uint8Array.from(atob(raw.dz), (ch) => ch.charCodeAt(0));
      const view = new DataView(bytes.buffer);
      const count = raw.cols * raw.rows;
      raw.dzdx = new Float32Array(count);
      raw.dzdy = new Float32Array(count);
      for (let i = 0; i < count; i += 1) {
        raw.dzdx[i] = view.getInt16(i * 2, true) / 10000;
        raw.dzdy[i] = view.getInt16((count + i) * 2, true) / 10000;
      }
    }
    return raw;
  }

  function sampleGrade(info, lat, lon) {
    const radius = 20037508.342789244;
    const x = (lon * radius) / 180;
    const y = Math.log(Math.tan(((90 + lat) * Math.PI) / 360)) * (radius / Math.PI);
    const step = (greenGrids && greenGrids.stepM) || 1;
    const col = (x - info.minx) / step;
    const row = (info.maxy - y) / step;
    if (col < 0 || row < 0 || col > info.cols - 1 || row > info.rows - 1) return null;
    const c0 = Math.floor(col);
    const r0 = Math.floor(row);
    const c1 = Math.min(c0 + 1, info.cols - 1);
    const r1 = Math.min(r0 + 1, info.rows - 1);
    const tc = col - c0;
    const tr = row - r0;
    function mix(arr) {
      const at = (r, c) => arr[r * info.cols + c];
      return (
        at(r0, c0) * (1 - tc) * (1 - tr) +
        at(r0, c1) * tc * (1 - tr) +
        at(r1, c0) * (1 - tc) * tr +
        at(r1, c1) * tc * tr
      );
    }
    return { dzdx: mix(info.dzdx), dzdy: mix(info.dzdy) };
  }

  function moveMeters(lat, lon, bearing, meters) {
    const rad = (bearing * Math.PI) / 180;
    const latM = 111320;
    const lonM = 111320 * Math.cos((lat * Math.PI) / 180);
    return {
      lat: lat + (Math.cos(rad) * meters) / latM,
      lon: lon + (Math.sin(rad) * meters) / lonM,
    };
  }

  function pointInRing(lat, lon, ring) {
    if (!ring || ring.length < 3) return true;
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
      const yi = ring[i][0];
      const xi = ring[i][1];
      const yj = ring[j][0];
      const xj = ring[j][1];
      const crosses = yi > lat !== yj > lat;
      if (crosses && lon < ((xj - xi) * (lat - yi)) / (yj - yi || 1e-12) + xi) inside = !inside;
    }
    return inside;
  }

  function enFrom(lat, lon, originLat, originLon) {
    const latM = 111320;
    const lonM = 111320 * Math.cos((originLat * Math.PI) / 180);
    return { x: (lon - originLon) * lonM, y: (lat - originLat) * latM };
  }

  function llFrom(x, y, originLat, originLon) {
    const latM = 111320;
    const lonM = 111320 * Math.cos((originLat * Math.PI) / 180);
    return { lat: originLat + y / latM, lon: originLon + x / lonM };
  }

  function simulatePutt(info, ball, hole, aimDeg, speed) {
    const originLat = ball.lat;
    const originLon = ball.lon;
    let px = 0;
    let py = 0;
    const holeM = enFrom(hole.lat, hole.lon, originLat, originLon);
    const rad = (aimDeg * Math.PI) / 180;
    let vx = Math.sin(rad) * speed;
    let vy = Math.cos(rad) * speed;
    const path = [[ball.lat, ball.lon]];
    let minDist = Infinity;
    let endDist = Infinity;
    const gravity = 9.81;
    const friction = (1.83 * 1.83) / (2 * 10 * 0.3048);
    const dt = 0.06;
    for (let step = 0; step < 240; step += 1) {
      const here = llFrom(px, py, originLat, originLon);
      const grade = sampleGrade(info, here.lat, here.lon);
      const pace = Math.hypot(vx, vy);
      if (pace < 0.08) break;
      const dzdx = grade ? grade.dzdx : 0;
      const dzdy = grade ? grade.dzdy : 0;
      vx += (-gravity * dzdx - (friction * vx) / pace) * dt;
      vy += (-gravity * dzdy - (friction * vy) / pace) * dt;
      px += vx * dt;
      py += vy * dt;
      const miss = Math.hypot(px - holeM.x, py - holeM.y);
      if (miss < minDist) minDist = miss;
      endDist = miss;
      if (step % 2 === 0) {
        const spot = llFrom(px, py, originLat, originLon);
        path.push([spot.lat, spot.lon]);
      }
    }
    return { path, minDist, endDist };
  }

  function solvePutt(info, ball, hole) {
    const dist = metersBetween(ball.lat, ball.lon, hole.lat, hole.lon);
    if (dist < 0.45) {
      return { path: [[ball.lat, ball.lon], [hole.lat, hole.lon]], offsetM: 0, dist, minDist: 0 };
    }
    const direct = bearingDeg({ lat: ball.lat, lng: ball.lon }, { lat: hole.lat, lng: hole.lon });
    const friction = (1.83 * 1.83) / (2 * 10 * 0.3048);
    const flat = Math.sqrt(2 * friction * dist);
    let best = null;
    function consider(aim, speed) {
      const sim = simulatePutt(info, ball, hole, aim, speed);
      const score = sim.minDist + 0.5 * sim.endDist;
      if (!best || score < best.score) best = { score, aim, speed, sim };
    }
    for (let aim = -36; aim <= 36; aim += 3) {
      for (let pace = 0.75; pace <= 1.7; pace += 0.15) consider(direct + aim, flat * pace);
    }
    const aim0 = best.aim;
    const speed0 = best.speed;
    for (let aim = aim0 - 3; aim <= aim0 + 3; aim += 0.75) {
      for (let pace = 0.88; pace <= 1.12; pace += 0.06) consider(aim, speed0 * pace);
    }
    let rel = best.aim - direct;
    if (rel > 180) rel -= 360;
    if (rel < -180) rel += 360;
    const path = best.sim.path.slice();
    if (best.sim.minDist < 0.5 && best.sim.endDist < 0.9) path.push([hole.lat, hole.lon]);
    return {
      path,
      offsetM: dist * Math.sin((rel * Math.PI) / 180),
      dist,
      minDist: best.sim.minDist,
    };
  }

  function formatPutt(result) {
    const lengthFt = result.dist * 3.280839895;
    const length = lengthFt < 1.5 ? "a tap-in" : Math.round(lengthFt) + " ft putt";
    if (result.dist < 0.5) return "Ball is at the hole";
    if (result.minDist > 1.2) return "This slope won't finish in the hole · " + length;
    const feet = Math.abs(result.offsetM) * 3.280839895;
    if (feet < 0.4) return "Start it at the hole · " + length;
    const startSide = result.offsetM > 0 ? "right" : "left";
    const breakSide = result.offsetM > 0 ? "left" : "right";
    const amount = feet < 10 ? feet.toFixed(1).replace(/\.0$/, "") : String(Math.round(feet));
    return "Start it " + amount + " ft " + startSide + " · breaks " + breakSide + " · " + length;
  }

  function startingBall(course, hole, pinLat, pinLon) {
    const target = greenTargets[course] && greenTargets[course][hole];
    if (!target) return { lat: pinLat, lon: pinLon };
    const away = bearingDeg({ lat: pinLat, lng: pinLon }, { lat: target.teeLat, lng: target.teeLon });
    let chosen = { lat: pinLat, lon: pinLon };
    for (let meters = 3; meters <= 16; meters += 1) {
      const spot = moveMeters(pinLat, pinLon, away, meters);
      if (target.ring && !pointInRing(spot.lat, spot.lon, target.ring)) break;
      chosen = spot;
      if (meters >= 10) break;
    }
    return chosen;
  }

  function drawPutt(path) {
    if (puttShade) map.removeLayer(puttShade);
    if (puttLine) map.removeLayer(puttLine);
    puttShade = L.polyline(path, { color: "#111", weight: 9, opacity: 0.55, interactive: false }).addTo(map);
    puttLine = L.polyline(path, { color: "#ffe56a", weight: 4, opacity: 1, interactive: false }).addTo(map);
  }

  function updatePutt() {
    if (!ballMarker || !pinMarker || !selectedHole) return;
    const course = selectedHole.course;
    const hole = selectedHole.hole;
    const info = gridFor(course, hole);
    const ball = ballMarker.getLatLng();
    const pin = pinMarker.getLatLng();
    const ring = greenTargets[course] && greenTargets[course][hole] && greenTargets[course][hole].ring;
    if (ring && pointInRing(ball.lat, ball.lng, ring)) ballMarker._good = ball;
    if (ring && pointInRing(pin.lat, pin.lng, ring)) pinMarker._good = pin;
    if (!info) return;
    const result = solvePutt(info, { lat: ball.lat, lon: ball.lng }, { lat: pin.lat, lon: pin.lng });
    drawPutt(result.path);
    puttRead = formatPutt(result);
    if (scoreRoll) scoreRoll.textContent = puttRead;
  }

  function snapPuttMarker(marker) {
    const ring = selectedHole && greenTargets[selectedHole.course] && greenTargets[selectedHole.course][selectedHole.hole].ring;
    const here = marker.getLatLng();
    if (ring && !pointInRing(here.lat, here.lng, ring) && marker._good) marker.setLatLng(marker._good);
  }

  function setupPutt(course, hole) {
    clearPuttMarkers();
    const target = greenTargets[course] && greenTargets[course][hole];
    const info = gridFor(course, hole);
    if (!target || !info) return;
    const pin = { lat: target.lat, lon: target.lon };
    const ball = startingBall(course, hole, pin.lat, pin.lon);
    ballMarker = L.marker([ball.lat, ball.lon], {
      draggable: true,
      icon: L.divIcon({
        className: "putt-icon",
        html: '<div class="putt-ball"></div>',
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      }),
      zIndexOffset: 900,
      title: "Drag the ball",
    }).addTo(map);
    pinMarker = L.marker([pin.lat, pin.lon], {
      draggable: true,
      icon: L.divIcon({
        className: "putt-icon",
        html: '<div class="putt-flag"><i></i></div>',
        iconSize: [22, 28],
        iconAnchor: [3, 26],
      }),
      zIndexOffset: 880,
      title: "Drag the hole",
    }).addTo(map);
    ballMarker._good = ballMarker.getLatLng();
    pinMarker._good = pinMarker.getLatLng();
    ballMarker.on("drag", updatePutt);
    pinMarker.on("drag", updatePutt);
    ballMarker.on("dragend", () => {
      snapPuttMarker(ballMarker);
      updatePutt();
    });
    pinMarker.on("dragend", () => {
      snapPuttMarker(pinMarker);
      updatePutt();
    });
    updatePutt();
  }

  function clearPuttMarkers() {
    [ballMarker, pinMarker, puttLine, puttShade].forEach((layer) => {
      if (layer) map.removeLayer(layer);
    });
    ballMarker = null;
    pinMarker = null;
    puttLine = null;
    puttShade = null;
    puttRead = "";
  }

  function clearPutt() {
    clearPuttMarkers();
    if (selectedHole && scoreRoll) scoreRoll.textContent = rollPhrase(selectedHole.course, selectedHole.hole);
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

  function toLocalMeters(lat, lon, originLat) {
    const latM = 111320;
    const lonM = 111320 * Math.cos((originLat * Math.PI) / 180);
    return { x: lon * lonM, y: lat * latM };
  }

  // Front and back are where the shot from you through the pin enters and leaves the green.
  function greenEdges(userLat, userLon, pinLat, pinLon, ring) {
    if (!ring || ring.length < 4) return null;
    const P = toLocalMeters(userLat, userLon, userLat);
    const C = toLocalMeters(pinLat, pinLon, userLat);
    const dx = C.x - P.x;
    const dy = C.y - P.y;
    const length = Math.hypot(dx, dy);
    if (length < 1) return null;
    const hits = [];
    for (let i = 0; i < ring.length - 1; i += 1) {
      const A = toLocalMeters(ring[i][0], ring[i][1], userLat);
      const B = toLocalMeters(ring[i + 1][0], ring[i + 1][1], userLat);
      const ex = B.x - A.x;
      const ey = B.y - A.y;
      const den = dx * ey - dy * ex;
      if (Math.abs(den) < 1e-6) continue;
      const ax = A.x - P.x;
      const ay = A.y - P.y;
      const t = (ax * ey - ay * ex) / den;
      const u = (ax * dy - ay * dx) / den;
      if (t > 0.001 && u >= -0.0001 && u <= 1.0001) hits.push(t);
    }
    if (hits.length < 2) return null;
    return {
      front: Math.round(Math.min.apply(null, hits) * length * M_TO_YD),
      back: Math.round(Math.max.apply(null, hits) * length * M_TO_YD),
    };
  }

  function assignGreenRings(greensFc) {
    const rings = (greensFc.features || [])
      .map((feature) => {
        const coords =
          feature.geometry &&
          feature.geometry.coordinates &&
          feature.geometry.coordinates[0];
        if (!coords || coords.length < 4) return null;
        const ring = coords.map((c) => [c[1], c[0]]);
        const n = ring.length - 1;
        let lat = 0;
        let lon = 0;
        for (let i = 0; i < n; i += 1) {
          lat += ring[i][0];
          lon += ring[i][1];
        }
        return { ring, lat: lat / n, lon: lon / n };
      })
      .filter(Boolean);
    const pins = [];
    Object.keys(greenTargets).forEach((course) => {
      Object.keys(greenTargets[course]).forEach((hole) => {
        pins.push(greenTargets[course][hole]);
      });
    });
    const pairs = [];
    pins.forEach((pin) => {
      rings.forEach((ring) => {
        pairs.push({
          pin,
          ring,
          d: yardsBetween(pin.lat, pin.lon, ring.lat, ring.lon),
        });
      });
    });
    pairs.sort((a, b) => a.d - b.d);
    const usedPins = new Set();
    const usedRings = new Set();
    pairs.forEach((pair) => {
      if (pair.d > 80 || usedPins.has(pair.pin) || usedRings.has(pair.ring)) return;
      usedPins.add(pair.pin);
      usedRings.add(pair.ring);
      pair.pin.ring = pair.ring.ring;
    });
  }

  function showGreenEdges(edges) {
    const on = !!(edges && !markTarget);
    if (yhFrontWrap) yhFrontWrap.hidden = !on;
    if (yhBackWrap) yhBackWrap.hidden = !on;
    if (!on) return;
    yhFront.textContent = String(edges.front);
    yhBack.textContent = String(edges.back);
  }

  function updateMarkButton() {
    if (!btnCenter) return;
    btnCenter.hidden = !selectedHole || !markTarget;
  }

  function updateYardageHud() {
    paintWind();
    if (!selectedHole) {
      yardageHud.hidden = true;
      showGreenEdges(null);
      updateMarkButton();
      if (aimLine) {
        map.removeLayer(aimLine);
        aimLine = null;
      }
      if (greenMarker) {
        map.removeLayer(greenMarker);
        greenMarker = null;
      }
      if (markMarker) {
        map.removeLayer(markMarker);
        markMarker = null;
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
    const hcp = handicapFor(course, hole);
    yhHole.textContent = hcp != null ? `Hole ${hole} · Hcp ${hcp}` : `Hole ${hole}`;

    const scorecard = `Par ${t.props.par || "—"} · ${playsLine(course, hole) || teeName(teeId)}`;

    if (!lastUser) {
      yhYards.textContent = "—";
      showGreenEdges(null);
      updateMarkButton();
      yhMeta.textContent = "Waiting for GPS · " + scorecard;
      return;
    }

    const accYd =
      lastUser.accuracy != null
        ? Math.round(lastUser.accuracy * M_TO_YD)
        : null;
    const gpsBit = "GPS" + (accYd != null ? ` ±${accYd}` : "");
    const centerYds = Math.round(
      yardsBetween(lastUser.lat, lastUser.lon, t.lat, t.lon)
    );
    let yds = centerYds;
    if (markTarget) {
      yds = Math.round(
        yardsBetween(lastUser.lat, lastUser.lon, markTarget.lat, markTarget.lng)
      );
      showGreenEdges(null);
      yhMeta.textContent = gpsBit + " · to the mark · " + scorecard;
    } else {
      const edges = greenEdges(lastUser.lat, lastUser.lon, t.lat, t.lon, t.ring);
      showGreenEdges(edges);
      yhMeta.textContent = gpsBit + " · " + scorecard;
    }
    updateMarkButton();
    yhYards.textContent = String(yds);

    const from = [lastUser.lat, lastUser.lon];
    const to = markTarget
      ? [markTarget.lat, markTarget.lng]
      : [t.lat, t.lon];
    if (!aimLine) {
      aimLine = L.polyline([from, to], {
        color: markTarget ? "#ffb020" : "#ffffff",
        weight: 2,
        opacity: 0.85,
        dashArray: "6 8",
      }).addTo(map);
    } else {
      aimLine.setStyle({ color: markTarget ? "#ffb020" : "#ffffff" });
      aimLine.setLatLngs([from, to]);
      if (!map.hasLayer(aimLine)) aimLine.addTo(map);
    }

    if (markTarget) {
      if (!markMarker) {
        markMarker = L.circleMarker(markTarget, {
          radius: 7,
          color: "#ffb020",
          weight: 2,
          fillColor: "#ffb020",
          fillOpacity: 0.95,
          interactive: false,
        }).addTo(map);
      } else {
        markMarker.setLatLng(markTarget);
        if (!map.hasLayer(markMarker)) markMarker.addTo(map);
      }
    } else if (markMarker) {
      map.removeLayer(markMarker);
      markMarker = null;
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
    L.geoJSON(fc, { style }).addTo(group);
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

  const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  let wind = null;

  function compassName(deg) {
    const turn = ((deg % 360) + 360) % 360;
    return COMPASS[Math.round(turn / 22.5) % 16];
  }

  function shotBearing(course, hole) {
    const t = greenTargets[course] && greenTargets[course][hole];
    if (!t || t.teeLat == null) return null;
    const bearing = bearingDeg(
      { lat: t.teeLat, lng: t.teeLon },
      { lat: t.lat, lng: t.lon }
    );
    return bearing == null ? null : ((bearing % 360) + 360) % 360;
  }

  function windPhrase() {
    if (!wind || wind.mph == null) return "";
    if (wind.mph < 1) return "Calm";
    const gust =
      wind.gust != null && wind.gust >= wind.mph + 3 ? ", gusting to " + wind.gust : "";
    if (wind.deg == null) return "Variable" + gust;
    let shot = null;
    if (selectedHole) shot = shotBearing(selectedHole.course, selectedHole.hole);
    if (shot == null) return "from the " + compassName(wind.deg) + gust;
    const rel = ((wind.deg - shot) % 360 + 360) % 360;
    const into = Math.cos((rel * Math.PI) / 180);
    const fromRight = Math.sin((rel * Math.PI) / 180);
    const cross = Math.abs(fromRight) >= 0.35;
    const side = fromRight >= 0 ? "the right" : "the left";
    let how = "off " + side;
    if (into >= 0.5) how = cross ? "into you, off " + side : "into you";
    else if (into <= -0.5) how = cross ? "helping, off " + side : "helping";
    return how + gust;
  }

  function paintWind() {
    const chip = document.getElementById("wind-chip");
    const arrow = document.getElementById("wind-arrow");
    const degEl = document.getElementById("wind-deg");
    const rhEl = document.getElementById("wind-rh");
    const speedEl = document.getElementById("wind-speed");
    const fromEl = document.getElementById("wind-from");
    if (!chip || !speedEl || !fromEl) return;
    if (!wind) {
      speedEl.textContent = "…";
      fromEl.textContent = "at the course";
      return;
    }
    if (wind.mph == null) {
      speedEl.textContent = "—";
      fromEl.textContent = "Wind unavailable";
      if (arrow) arrow.hidden = true;
      return;
    }
    speedEl.replaceChildren();
    speedEl.append(document.createTextNode(wind.mph < 1 ? "Calm" : String(wind.mph)));
    if (wind.mph >= 1) {
      const unit = document.createElement("span");
      unit.className = "wind-unit";
      unit.textContent = "mph";
      speedEl.append(unit);
    }
    if (degEl) degEl.textContent = wind.deg == null ? "Wind" : wind.deg + "°";
    if (rhEl) rhEl.textContent = wind.rh == null ? "" : wind.rh + "% rh";
    fromEl.textContent = windPhrase();
    if (arrow) {
      arrow.hidden = wind.deg == null || wind.mph < 1;
      if (!arrow.hidden) {
        arrow.style.transform = "rotate(" + ((wind.deg + 180) % 360) + "deg)";
      }
    }
    const spoken = [
      wind.mph < 1 ? "Calm" : wind.mph + " miles per hour",
      wind.deg == null ? "" : "from " + wind.deg + " degrees",
      wind.rh == null ? "" : wind.rh + " percent humidity",
      fromEl.textContent,
    ]
      .filter(Boolean)
      .join(", ");
    chip.setAttribute("aria-label", spoken);
  }

  function mphFromKmh(value) {
    const n = Number(value);
    if (!isFinite(n)) return null;
    return Math.round(n * 0.621371);
  }

  async function loadWind() {
    const res = await fetch("https://api.weather.gov/stations/KPTK/observations/latest", {
      headers: { Accept: "application/geo+json" },
    });
    if (!res.ok) throw new Error("wind");
    const data = await res.json();
    const props = data.properties || {};
    const speed = props.windSpeed && props.windSpeed.value;
    const gust = props.windGust && props.windGust.value;
    const dir = props.windDirection && props.windDirection.value;
    const rh = props.relativeHumidity && props.relativeHumidity.value;
    wind = {
      mph: speed == null ? null : mphFromKmh(speed),
      gust: gust == null ? null : mphFromKmh(gust),
      deg: dir == null ? null : Math.round(Number(dir)),
      rh: rh == null ? null : Math.round(Number(rh)),
    };
    paintWind();
  }

  function startWind() {
    const run = () =>
      loadWind().catch(() => {
        if (!wind) {
          wind = { mph: null, gust: null, deg: null, rh: null };
          paintWind();
        }
      });
    run();
    setInterval(run, 10 * 60 * 1000);
  }

  const YARD_RINGS = [
    { yards: 100, color: "#ff4d4d" },
    { yards: 150, color: "#ffffff" },
    { yards: 200, color: "#4da3ff" },
  ];
  let yardageRingLayers = [];

  function clearYardageRings() {
    yardageRingLayers.forEach((layer) => map.removeLayer(layer));
    yardageRingLayers = [];
  }

  function moveByYards(origin, bearing, yards) {
    const radius = 6371000;
    const dist = yards * 0.9144;
    const br = (bearing * Math.PI) / 180;
    const lat1 = (origin.lat * Math.PI) / 180;
    const lon1 = (origin.lng * Math.PI) / 180;
    const lat2 = Math.asin(
      Math.sin(lat1) * Math.cos(dist / radius) + Math.cos(lat1) * Math.sin(dist / radius) * Math.cos(br)
    );
    const lon2 =
      lon1 +
      Math.atan2(
        Math.sin(br) * Math.sin(dist / radius) * Math.cos(lat1),
        Math.cos(dist / radius) - Math.sin(lat1) * Math.sin(lat2)
      );
    return L.latLng((lat2 * 180) / Math.PI, (((lon2 * 180) / Math.PI + 540) % 360) - 180);
  }

  function greenMiddle(target) {
    const ring = target.ring;
    if (!ring || ring.length < 4) return L.latLng(target.lat, target.lon);
    const n = ring.length - 1;
    let lat = 0;
    let lon = 0;
    for (let i = 0; i < n; i += 1) {
      lat += ring[i][0];
      lon += ring[i][1];
    }
    return L.latLng(lat / n, lon / n);
  }

  function showYardageRings(course, hole) {
    clearYardageRings();
    const target = greenTargets[course] && greenTargets[course][hole];
    if (!target || target.teeLat == null) return;
    const green = greenMiddle(target);
    const tee = L.latLng(target.teeLat, target.teeLon);
    const bearing = bearingDeg(green, tee);
    if (bearing == null) return;
    const toTee = map.distance(green, tee) * M_TO_YD;
    YARD_RINGS.forEach((ring) => {
      if (ring.yards > toTee - 20) return;
      const pts = [];
      for (let turn = -58; turn <= 58; turn += 2) pts.push(moveByYards(green, bearing + turn, ring.yards));
      const shade = L.polyline(pts, {
        pane: "yardage",
        color: "#1a1408",
        weight: 2,
        opacity: 0.45,
        interactive: false,
      }).addTo(map);
      const line = L.polyline(pts, {
        pane: "yardage",
        color: ring.color,
        weight: 1,
        opacity: 1,
        interactive: false,
      }).addTo(map);
      const label = L.marker(moveByYards(green, bearing - 50, ring.yards), {
        pane: "yardage",
        interactive: false,
        icon: L.divIcon({
          className: "yard-ring-icon",
          html: `<div class="yard-pill y${ring.yards}">${ring.yards}</div>`,
          iconSize: [36, 20],
          iconAnchor: [18, 10],
        }),
      }).addTo(map);
      yardageRingLayers.push(shade, line, label);
    });
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
    if (btnReset) btnReset.hidden = !selectedHole;
    btnFly.textContent = flying ? "Stop" : "Fly over";
    btnFly.setAttribute("aria-pressed", flying ? "true" : "false");
    btnFly.setAttribute(
      "aria-label",
      flying ? "Stop the fly-over" : "Fly over this hole from tee to green"
    );
    updateVideoButton();
  }

  function updateVideoButton() {
    if (!btnVideo) return;
    btnVideo.hidden = !selectedHole;
    if (!selectedHole) return;
    btnVideo.setAttribute(
      "aria-label",
      "Play the flyover video for Wyndgate hole " + selectedHole.hole
    );
  }

  const holeVoice = new Audio();

  function voiceFile() {
    if (!selectedHole) return "";
    const tee = TEE_IDS.indexOf(teeId) === -1 ? "black" : teeId;
    return "voice-wyndgate-" + selectedHole.hole + "-" + tee + ".m4a";
  }

  function stopHoleVoice() {
    holeVoice.pause();
    holeVoice.removeAttribute("src");
    holeVoice.load();
  }

  function playSelectedVoice() {
    const file = voiceFile();
    if (!file) return;
    holeVoice.pause();
    holeVoice.src = file;
    holeVoice.muted = holeVideo.muted;
    holeVoice.volume = holeVideo.volume;
    holeVoice.play().catch(() => {});
  }

  function closeHoleVideo() {
    if (!videoModal || videoModal.hidden) return;
    stopHoleVoice();
    if (holeVideo) {
      holeVideo.pause();
      holeVideo.removeAttribute("src");
      holeVideo.load();
    }
    videoModal.hidden = true;
  }

  function playHoleVideo() {
    if (!selectedHole || !holeVideo || !videoModal) return;
    if (flying) stopFlyover();
    videoTitle.textContent = "The Wyndgate · Hole " + selectedHole.hole;
    // Reset the shared <video> so iOS Safari does not keep showing the previous
    // hole's last (green) frame when the new src is still loading.
    holeVideo.pause();
    holeVideo.src = "flyover-wyndgate-" + selectedHole.hole + ".mp4";
    try {
      holeVideo.currentTime = 0;
    } catch (_) {}
    holeVideo.load();
    videoModal.hidden = false;
    playSelectedVoice();
    const tryPlay = () => holeVideo.play().catch(() => {});
    tryPlay();
    holeVideo.addEventListener("loadeddata", tryPlay, { once: true });
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
    // "Fly over" is an explicit user action. Do not honor prefers-reduced-motion
    // by skipping the flight — that zeroed dive/cruise (common on iPhone with
    // Settings → Accessibility → Motion → Reduce Motion) and teleported the
    // camera to the green, looking like a stale end-of-hole view.
    const closeZoom = Math.min(19, map.getMaxZoom() || 19);
    const startZoom = map.getZoom();
    const dive = 1600;
    const cruise = Math.max(5200, Math.min(9000, meters * M_TO_YD * 14));
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

  function clearHoleSelection() {
    stopFlyover();
    stopListening();
    if (selectedHole) {
      const layer = holeIndex[selectedHole.course] && holeIndex[selectedHole.course][selectedHole.hole];
      if (layer) layer.closePopup();
    }
    document.querySelectorAll(".hole-btn.active").forEach((btn) => btn.classList.remove("active"));
    activeHoleBtn = null;
    selectedHole = null;
    markTarget = null;
    clearGreenBreak();
    clearYardageRings();
    lastHole.wyndgate = null;
    map.closePopup();
    updateYardageHud();
    showScoreEntry();
    updateFlyButton();
    const holes = Object.values(holeIndex[playingCourse] || {});
    if (holes.length) {
      map.fitBounds(L.featureGroup(holes).getBounds(), { padding: [30, 30] });
    }
  }

  function focusHole(course, n, btn) {
    const layer = holeIndex[course][n];
    if (!layer) return;
    stopFlyover();
    stopListening();
    markTarget = null;
    if (activeHoleBtn) activeHoleBtn.classList.remove("active");
    if (btn) {
      btn.classList.add("active");
      activeHoleBtn = btn;
    } else {
      const list = listHoles;
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
    showGreenBreak(course, n);
    showYardageRings(course, n);
  }

  function applyToggles() {
    const showH = togHoles.checked;
    const showP = togPaths.checked;
    const showF = togFairways.checked;

    setLayer(layers.holes, showH);
    setLayer(layers.labels, showH);
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
    buildHoleButtons(COURSE, listHoles);

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
      cardJson,
      slopeData,
      gridData,
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
      loadJSON("card.json"),
      loadJSON("green_slopes.json"),
      loadJSON("green_grids.json"),
    ]);
    card = cardJson;
    greenSlopes = slopeData;
    greenGrids = gridData;

    const attribEl = document.getElementById("attrib");
    const attribBase = meta.attribution + " · Green slope: USGS 3DEP";
    attribEl.dataset.base = attribBase;
    attribEl.textContent = attribBase + " · " + imageryCredit();

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
        return {
          color: HOLE,
          weight: 3.5,
          opacity: 0.95,
        };
      },
      onEachFeature(feature, layer) {
        const p = feature.properties;
        const coords = feature.geometry.coordinates;
        // OSM hole lines end at the green / pin end.
        const end = coords[coords.length - 1];
        const start = coords[0];
        greenTargets[p.course][p.hole] = {
          lon: end[0],
          lat: end[1],
          teeLon: start[0],
          teeLat: start[1],
          props: p,
        };
        if (p.par) pars[p.course][p.hole] = p.par;
        layer.bindPopup(popupHole(p));
        holeIndex[p.course][p.hole] = layer;
        layer.addTo(layers.holes);
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
        layer.addTo(layers.labels);
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

    assignGreenRings(greens);

    if (meta.clubhouse) {
      L.marker([meta.clubhouse.lat, meta.clubhouse.lon])
        .addTo(map)
        .bindPopup(
          `<strong>${meta.clubhouse.name}</strong><br/>${meta.clubhouse.address}`
        );
    }

    const allHoleLayers = Object.values(holeIndex.wyndgate);
    if (allHoleLayers.length) {
      const group = L.featureGroup(allHoleLayers);
      map.fitBounds(group.getBounds(), { padding: [30, 30] });
    }

    applyToggles();
    applyCardChoices();
    setPlayingCourse();
    startGps(false);
    startWind();
  }

  function setPlayingCourse() {
    playingCourse = COURSE;
    const panel = document.getElementById("course-wyndgate");
    const head = panel.querySelector(".course-head");
    if (head && scoreEntry.parentElement !== panel) {
      head.insertAdjacentElement("afterend", scoreEntry);
    }
  }

  function loadScores() {
    try {
      const raw = JSON.parse(localStorage.getItem(SCORE_KEY) || "{}");
      return { wyndgate: sanitizeCourse(raw.wyndgate) };
    } catch (err) {
      return { wyndgate: {} };
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

  function loadTee() {
    try {
      const saved = localStorage.getItem(TEE_KEY);
      if (TEE_IDS.indexOf(saved) !== -1) return saved;
    } catch (err) {
      /* keep the black tees */
    }
    return "black";
  }

  function loadHcp() {
    try {
      if (localStorage.getItem(HCP_KEY) === "women") return "women";
    } catch (err) {
      /* keep the men's card */
    }
    return "men";
  }

  function rememberChoice(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (err) {
      /* Private mode can block storage. */
    }
  }

  function holeCard(course, hole) {
    const holes = card && card.courses && card.courses[course] && card.courses[course].holes;
    if (!holes) return null;
    return holes[hole - 1] || null;
  }

  function teeName(id) {
    const row = card && card.tees && card.tees.find((tee) => tee.id === id);
    if (row) return row.name;
    return id ? id.charAt(0).toUpperCase() + id.slice(1) : "Tee";
  }

  function handicapFor(course, hole) {
    const info = holeCard(course, hole);
    if (!info) return null;
    if (hcpSet === "women") return info.hcpWomen;
    return info.hcpMen;
  }

  function ratingLine() {
    const row = card && card.tees && card.tees.find((tee) => tee.id === teeId);
    if (!row || row.yards == null) return "";
    const yards = Number(row.yards).toLocaleString("en-US");
    const women = hcpSet === "women" && row.ratingWomen != null;
    const rating = women ? row.ratingWomen : row.rating;
    const slope = women ? row.slopeWomen : row.slope;
    if (rating == null || slope == null) return yards + " yards";
    return yards + " yards · " + rating + " / " + slope;
  }

  function yardageFor(course, hole) {
    const info = holeCard(course, hole);
    if (!info || !info.yards || info.yards[teeId] == null) return null;
    return info.yards[teeId];
  }

  function playsFor(course, hole) {
    const info = holeCard(course, hole);
    if (!info || !info.elevFt) return null;
    return OUScore.playsLike(info.yards[teeId], info.elevFt[teeId], info.elevFt.green);
  }

  function playsLine(course, hole) {
    const yards = yardageFor(course, hole);
    if (yards == null) return "";
    const plays = OUScore.formatPlaysLike(playsFor(course, hole));
    return plays ? teeName(teeId) + " " + yards + " · " + plays : teeName(teeId) + " " + yards;
  }

  function holeFacts(course, hole) {
    const info = holeCard(course, hole);
    const par = (info && info.par) || (pars[course] && pars[course][hole]);
    const hcp = handicapFor(course, hole);
    const bits = [];
    if (par) bits.push("Par " + par);
    if (hcp != null) bits.push("Hcp " + hcp);
    const line = playsLine(course, hole);
    if (line) bits.push(line);
    return bits.join(" · ");
  }

  function applyCardChoices() {
    rememberChoice(TEE_KEY, teeId);
    rememberChoice(HCP_KEY, hcpSet);
    if (brandSub) brandSub.textContent = "Golf map · " + teeName(teeId) + " tees";
    if (cardNote) cardNote.textContent = ratingLine();
    paintAllScores();
    for (let n = 1; n <= 18; n += 1) refreshHolePopup(COURSE, n);
    updateYardageHud();
    showScoreEntry();
  }

  function paintScore(course, hole) {
    const btn = holeButtons[course][hole];
    if (!btn) return;
    const value = scores[course][hole];
    const hcp = handicapFor(course, hole);
    const yards = yardageFor(course, hole);
    const plays = playsFor(course, hole);
    btn.replaceChildren();
    const num = document.createElement("span");
    num.className = "hb-n";
    num.textContent = String(hole);
    const hcpMark = document.createElement("span");
    hcpMark.className = "hb-h";
    hcpMark.textContent = hcp == null ? "" : "H" + hcp;
    const yardsMark = document.createElement("span");
    yardsMark.className = "hb-y";
    yardsMark.textContent = plays ? String(plays.yards) : yards == null ? "" : String(yards);
    const mark = document.createElement("span");
    mark.className = "hb-s";
    mark.textContent = value == null ? "" : String(value);
    btn.append(num, hcpMark, yardsMark, mark);
    btn.classList.toggle("scored", value != null);
    const bits = ["Hole " + hole];
    if (hcp != null) bits.push("handicap " + hcp);
    if (plays) bits.push("plays " + plays.yards);
    else if (yards != null) bits.push(teeName(teeId) + " " + yards + " yards");
    if (value != null) bits.push(value + " strokes");
    btn.setAttribute("aria-label", bits.join(", "));
  }

  function paintAllScores() {
    [COURSE].forEach((course) => {
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
    const hcp = handicapFor(course, hole);
    scoreEntry.hidden = false;
    scoreHint.hidden = true;
    scoreKicker.textContent = COURSE_NAMES[course] || course;
    scoreHole.textContent =
      "Hole " +
      hole +
      (par ? " · Par " + par : "") +
      (hcp != null ? " · Hcp " + hcp : "") +
      (scoreCollapsed && saved != null ? " · " + saved : "");
    if (scorePlays) scorePlays.textContent = playsLine(course, hole);
    if (scoreRoll) scoreRoll.textContent = puttRead || rollPhrase(course, hole);
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

  togHoles.addEventListener("change", applyToggles);
  togPaths.addEventListener("change", applyToggles);
  togFairways.addEventListener("change", applyToggles);
  if (imagerySelect) {
    imagerySelect.addEventListener("change", () => setImagery(imagerySelect.value));
  }
  btnLocate.addEventListener("click", () => startGps(true));
  btnFly.addEventListener("click", flyOver);
  if (btnVideo) btnVideo.addEventListener("click", playHoleVideo);
  if (holeVideo) {
    holeVideo.addEventListener("pause", () => holeVoice.pause());
    holeVideo.addEventListener("play", () => {
      if (!holeVoice.src || holeVoice.ended) return;
      holeVoice.play().catch(() => {});
    });
    holeVideo.addEventListener("volumechange", () => {
      holeVoice.muted = holeVideo.muted;
      holeVoice.volume = holeVideo.volume;
    });
  }
  if (videoClose) videoClose.addEventListener("click", closeHoleVideo);
  if (videoModal) {
    videoModal.addEventListener("click", (event) => {
      if (event.target === videoModal) closeHoleVideo();
    });
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeHoleVideo();
  });
  btnCenter.addEventListener("click", () => {
    markTarget = null;
    updateYardageHud();
  });
  btnReset.addEventListener("click", clearHoleSelection);
  if (btnBreaks) btnBreaks.addEventListener("click", zoomGreenBreak);
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
  document.getElementById("clear-wyndgate").addEventListener("click", () => clearCourse(COURSE));
  if (teeSelect) {
    teeSelect.value = teeId;
    teeSelect.addEventListener("change", () => {
      if (TEE_IDS.indexOf(teeSelect.value) === -1) return;
      teeId = teeSelect.value;
      applyCardChoices();
      if (videoModal && !videoModal.hidden) playSelectedVoice();
    });
  }
  if (hcpSelect) {
    hcpSelect.value = hcpSet;
    hcpSelect.addEventListener("change", () => {
      hcpSet = hcpSelect.value === "women" ? "women" : "men";
      applyCardChoices();
    });
  }

  setPlayingCourse();

  init().catch((err) => {
    console.error(err);
    setGpsStatus("Could not load course map data.", "err");
  });
})();
