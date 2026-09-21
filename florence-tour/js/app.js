(function () {
  "use strict";

  const TOUR = window.TOUR;
  if (!TOUR) return;

  const STORAGE_KEY = `passi-progress:${TOUR.id}`;

  const state = {
    activeId: TOUR.stops[0].id,
    unlocked: new Set([TOUR.stops[0].id]),
    done: new Set(),
    listening: false,
    watchId: null,
    userLatLng: null,
    scriptOpen: false,
  };

  const els = {
    map: document.getElementById("map"),
    stopList: document.getElementById("stop-list"),
    geoStatus: document.getElementById("geo-status"),
    progress: document.getElementById("progress-label"),
    playerTitle: document.getElementById("player-title"),
    playerSub: document.getElementById("player-sub"),
    playBtn: document.getElementById("play-btn"),
    scrub: document.getElementById("scrub"),
    timeCur: document.getElementById("time-cur"),
    timeDur: document.getElementById("time-dur"),
    imHereBtn: document.getElementById("im-here-btn"),
    locateBtn: document.getElementById("locate-btn"),
    scriptToggle: document.getElementById("script-toggle"),
    scriptDrawer: document.getElementById("script-drawer"),
    scriptBody: document.getElementById("script-body"),
    walkCue: document.getElementById("walk-cue"),
    markDoneBtn: document.getElementById("mark-done-btn"),
    audio: document.getElementById("tour-audio"),
  };

  let map;
  let userMarker;
  let accuracyCircle;
  const stopMarkers = new Map();

  function loadProgress() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      state.unlocked = new Set(data.unlocked || [TOUR.stops[0].id]);
      state.done = new Set(data.done || []);
      if (data.activeId && TOUR.stops.some((s) => s.id === data.activeId)) {
        state.activeId = data.activeId;
      }
    } catch (_) {
      /* ignore */
    }
  }

  function saveProgress() {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        unlocked: [...state.unlocked],
        done: [...state.done],
        activeId: state.activeId,
      })
    );
  }

  function stopById(id) {
    return TOUR.stops.find((s) => s.id === id);
  }

  function activeStop() {
    return stopById(state.activeId);
  }

  function haversineMeters(aLat, aLng, bLat, bLng) {
    const R = 6371000;
    const toRad = (d) => (d * Math.PI) / 180;
    const dLat = toRad(bLat - aLat);
    const dLng = toRad(bLng - aLng);
    const x =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(x));
  }

  function formatTime(sec) {
    if (!Number.isFinite(sec) || sec < 0) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  function pinIcon(stop, kind) {
    const cls = `marker-pin marker-pin--${kind}`;
    return L.divIcon({
      className: "",
      html: `<div class="${cls}" aria-hidden="true"><span>${stop.order}</span></div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 28],
      popupAnchor: [0, -28],
    });
  }

  function markerKind(stop) {
    if (stop.id === state.activeId) return "active";
    if (state.done.has(stop.id)) return "done";
    if (state.unlocked.has(stop.id)) return "unlocked";
    return "locked";
  }

  function initMap() {
    map = L.map(els.map, {
      zoomControl: false,
      attributionControl: true,
    }).setView(TOUR.mapCenter, TOUR.mapZoom);

    L.control.zoom({ position: "topright" }).addTo(map);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);

    TOUR.stops.forEach((stop) => {
      const marker = L.marker([stop.lat, stop.lng], {
        icon: pinIcon(stop, markerKind(stop)),
        title: stop.name,
      }).addTo(map);

      marker.on("click", () => activateStop(stop.id));
      stopMarkers.set(stop.id, marker);
    });

    const bounds = L.latLngBounds(TOUR.stops.map((s) => [s.lat, s.lng]));
    map.fitBounds(bounds.pad(0.18));
  }

  function refreshMarkers() {
    TOUR.stops.forEach((stop) => {
      const marker = stopMarkers.get(stop.id);
      if (marker) marker.setIcon(pinIcon(stop, markerKind(stop)));
    });
  }

  function renderStopList() {
    els.stopList.innerHTML = "";
    TOUR.stops.forEach((stop) => {
      const unlocked = state.unlocked.has(stop.id);
      const done = state.done.has(stop.id);
      const active = stop.id === state.activeId;

      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "stop-item";
      if (active) btn.classList.add("is-active");
      if (!unlocked) btn.classList.add("is-locked");
      if (unlocked && !done) btn.classList.add("is-unlocked");
      if (done) btn.classList.add("is-done");

      let badge = "Locked";
      if (done) badge = "Heard";
      else if (unlocked) badge = "Unlocked";

      btn.innerHTML = `
        <span class="stop-num">${stop.order}</span>
        <span class="stop-meta">
          <strong>${stop.name}</strong>
          <small>${stop.walkFromPrev}</small>
        </span>
        <span class="stop-badge">${badge}</span>
      `;
      btn.addEventListener("click", () => activateStop(stop.id));
      li.appendChild(btn);
      els.stopList.appendChild(li);
    });

    const unlockedCount = state.unlocked.size;
    const doneCount = state.done.size;
    els.progress.textContent = `${doneCount}/${TOUR.stops.length} heard · ${unlockedCount} unlocked`;
  }

  function renderScript(stop) {
    els.scriptBody.innerHTML = "";
    stop.script.forEach((para, i) => {
      const p = document.createElement("p");
      p.dataset.index = String(i);
      p.textContent = para;
      els.scriptBody.appendChild(p);
    });
  }

  function highlightScript(progress) {
    const paras = els.scriptBody.querySelectorAll("p");
    if (!paras.length) return;
    const idx = Math.min(paras.length - 1, Math.floor(progress * paras.length));
    paras.forEach((p, i) => p.classList.toggle("is-current", i === idx));
  }

  function selectStop(id, opts = {}) {
    const stop = stopById(id);
    if (!stop) return;

    const unlocked = state.unlocked.has(id);
    state.activeId = id;
    saveProgress();

    els.playerTitle.textContent = `${stop.order}. ${stop.name}`;
    els.playerSub.textContent = unlocked
      ? "Tap ▶ or the stop number to hear the guide"
      : "Locked — tap the stop again to unlock & play, or I’m here";
    els.walkCue.textContent = stop.walkFromPrev;

    renderScript(stop);
    highlightScript(0);

    els.playBtn.disabled = !unlocked;
    els.scrub.disabled = !unlocked;
    els.markDoneBtn.disabled = !unlocked;
    els.imHereBtn.disabled = unlocked;

    const switching =
      els.audio.dataset.stopId && els.audio.dataset.stopId !== stop.id;
    if (switching && !els.audio.paused) {
      els.audio.pause();
      updatePlayButton();
    }

    if (unlocked) {
      const abs = new URL(stop.audio, window.location.href).href;
      if (els.audio.dataset.stopId !== stop.id) {
        els.audio.src = abs;
        els.audio.dataset.stopId = stop.id;
        els.audio.load();
        els.timeDur.textContent = formatTime(stop.durationSec);
        els.scrub.value = 0;
        els.timeCur.textContent = "0:00";
      }
    } else {
      els.audio.removeAttribute("src");
      els.audio.dataset.stopId = "";
      els.timeDur.textContent = formatTime(stop.durationSec);
      els.scrub.value = 0;
      els.timeCur.textContent = "0:00";
    }

    renderStopList();
    refreshMarkers();

    if (opts.pan !== false && map) {
      map.panTo([stop.lat, stop.lng], { animate: true });
    }

    if (opts.autoplay && unlocked) {
      playCurrent();
    }
  }

  /** Tap a stop number/pin: unlock if needed, then play. */
  function activateStop(id) {
    const stop = stopById(id);
    if (!stop) return;

    if (!state.unlocked.has(id)) {
      state.unlocked.add(id);
      saveProgress();
      setGeoStatus(`Unlocked: ${stop.shortName} (tapped)`);
    }

    selectStop(id, { autoplay: true });
  }

  let playToken = 0;

  function playCurrent() {
    const stop = activeStop();
    if (!stop || !state.unlocked.has(stop.id)) return;

    const token = ++playToken;
    const abs = new URL(stop.audio, window.location.href).href;
    // Always (re)assign src so retries recover from a failed load / dead tunnel
    if (els.audio.dataset.stopId !== stop.id || !els.audio.getAttribute("src") || els.audio.error) {
      els.audio.src = abs;
      els.audio.dataset.stopId = stop.id;
      els.audio.load();
    }
    els.audio.volume = 1;

    const tryPlay = () => {
      if (token !== playToken) return;
      if (els.audio.error) {
        els.playerSub.textContent = "Audio failed — tap ▶ to retry";
        setGeoStatus("Could not load audio file. Tap ▶ again.");
        updatePlayButton();
        return;
      }
      const p = els.audio.play();
      if (p && typeof p.then === "function") {
        p.then(() => {
          if (token !== playToken) return;
          els.playerSub.textContent = "Playing — read along with the script";
          updatePlayButton();
        }).catch(() => {
          if (token !== playToken) return;
          els.playerSub.textContent = "Tap ▶ to start audio";
          setGeoStatus("Tap the ▶ button to play — browser blocked autoplay.");
          updatePlayButton();
        });
      } else {
        updatePlayButton();
      }
    };

    if (els.audio.readyState >= 2) {
      tryPlay();
    } else {
      els.audio.addEventListener("canplay", tryPlay, { once: true });
      setTimeout(tryPlay, 400);
    }
  }

  function unlockStop(id, reason) {
    if (state.unlocked.has(id)) return false;
    state.unlocked.add(id);
    saveProgress();
    if (els.geoStatus) {
      const stop = stopById(id);
      els.geoStatus.textContent = `Unlocked: ${stop.shortName} (${reason})`;
    }
    if (state.activeId === id) selectStop(id, { pan: false });
    else {
      renderStopList();
      refreshMarkers();
    }
    return true;
  }

  function checkProximity(lat, lng) {
    TOUR.stops.forEach((stop) => {
      if (state.unlocked.has(stop.id)) return;
      const d = haversineMeters(lat, lng, stop.lat, stop.lng);
      if (d <= TOUR.unlockRadiusMeters) {
        unlockStop(stop.id, `${Math.round(d)} m away`);
      }
    });
  }

  function updateUserLocation(lat, lng, accuracy) {
    state.userLatLng = { lat, lng };
    checkProximity(lat, lng);

    const latlng = L.latLng(lat, lng);
    if (!userMarker) {
      userMarker = L.marker(latlng, {
        icon: L.divIcon({
          className: "",
          html: '<div class="user-dot" title="You"></div>',
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        }),
        zIndexOffset: 1000,
      }).addTo(map);
      accuracyCircle = L.circle(latlng, {
        radius: accuracy || 40,
        color: "#3b82f6",
        weight: 1,
        fillOpacity: 0.08,
      }).addTo(map);
    } else {
      userMarker.setLatLng(latlng);
      accuracyCircle.setLatLng(latlng);
      if (accuracy) accuracyCircle.setRadius(accuracy);
    }
  }

  function setGeoStatus(msg) {
    if (els.geoStatus) els.geoStatus.textContent = msg;
  }

  function startWatching() {
    if (!navigator.geolocation) {
      setGeoStatus("GPS unavailable — use I’m here to unlock stops.");
      return;
    }
    if (state.watchId != null) return;

    setGeoStatus("Requesting location…");
    state.listening = true;
    state.watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        updateUserLocation(latitude, longitude, accuracy);
        setGeoStatus(`GPS on · ±${Math.round(accuracy || 0)} m · unlock within ${TOUR.unlockRadiusMeters} m`);
      },
      (err) => {
        state.listening = false;
        const tip = "Use I’m here to unlock while testing.";
        if (err.code === 1) setGeoStatus(`Location denied. ${tip}`);
        else setGeoStatus(`Location error. ${tip}`);
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
  }

  function locateOnce() {
    if (!navigator.geolocation) {
      setGeoStatus("GPS unavailable on this device.");
      return;
    }
    setGeoStatus("Finding you…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        updateUserLocation(latitude, longitude, accuracy);
        map.setView([latitude, longitude], Math.max(map.getZoom(), 16));
        setGeoStatus(`Centered on you · ±${Math.round(accuracy || 0)} m`);
        startWatching();
      },
      () => setGeoStatus("Could not get a fix — try I’m here instead."),
      { enableHighAccuracy: true, timeout: 12000 }
    );
  }

  function updatePlayButton() {
    const playing = els.audio && !els.audio.paused && !els.audio.ended;
    els.playBtn.textContent = playing ? "❚❚" : "▶";
    els.playBtn.setAttribute("aria-label", playing ? "Pause" : "Play");
  }

  function togglePlay() {
    const stop = activeStop();
    if (!stop || !state.unlocked.has(stop.id)) {
      if (stop) activateStop(stop.id);
      return;
    }
    if (els.audio.paused || els.audio.ended) {
      playCurrent();
    } else {
      els.audio.pause();
      els.playerSub.textContent = "Paused";
      updatePlayButton();
    }
  }

  function onTimeUpdate() {
    const a = els.audio;
    if (!a.duration) return;
    const pct = (a.currentTime / a.duration) * 100;
    els.scrub.value = String(pct);
    els.timeCur.textContent = formatTime(a.currentTime);
    els.timeDur.textContent = formatTime(a.duration);
    highlightScript(a.currentTime / a.duration);
  }

  function markDone() {
    const stop = activeStop();
    if (!stop || !state.unlocked.has(stop.id)) return;
    state.done.add(stop.id);
    const next = TOUR.stops.find((s) => s.order === stop.order + 1);
    saveProgress();
    renderStopList();
    refreshMarkers();
    if (next) {
      state.unlocked.add(next.id);
      saveProgress();
      // Do not autoplay here — browsers block play() outside a tap. Cue the next stop clearly.
      selectStop(next.id, { autoplay: false });
      els.playerSub.textContent = `Next: ${next.shortName} — tap ▶ to play`;
      setGeoStatus(`Ready for stop ${next.order}: ${next.shortName}. Tap ▶.`);
      els.playBtn.disabled = false;
      els.playBtn.focus();
    } else {
      els.playerSub.textContent = "Tour complete — grazie for walking with Passi";
      setGeoStatus("All stops heard.");
      renderStopList();
      refreshMarkers();
    }
  }

  function imHere() {
    const stop = activeStop();
    if (!stop) return;
    activateStop(stop.id);
    state.scriptOpen = true;
    els.scriptDrawer.classList.add("is-open");
    els.scriptToggle.textContent = "Hide script";
  }

  function toggleScript() {
    state.scriptOpen = !state.scriptOpen;
    els.scriptDrawer.classList.toggle("is-open", state.scriptOpen);
    els.scriptToggle.textContent = state.scriptOpen ? "Hide script" : "Show script";
  }

  function bindEvents() {
    els.playBtn.addEventListener("click", togglePlay);
    els.imHereBtn.addEventListener("click", imHere);
    els.locateBtn.addEventListener("click", locateOnce);
    els.scriptToggle.addEventListener("click", toggleScript);
    els.markDoneBtn.addEventListener("click", markDone);

    els.scrub.addEventListener("input", () => {
      if (!els.audio.duration) return;
      els.audio.currentTime = (Number(els.scrub.value) / 100) * els.audio.duration;
    });

    els.audio.addEventListener("timeupdate", onTimeUpdate);
    els.audio.addEventListener("play", updatePlayButton);
    els.audio.addEventListener("pause", updatePlayButton);
    els.audio.addEventListener("ended", () => {
      updatePlayButton();
      markDone();
    });
    els.audio.addEventListener("error", () => {
      const stop = activeStop();
      const name = stop ? stop.shortName : "this stop";
      els.playerSub.textContent = `Audio failed for ${name} — tap ▶ to retry`;
      setGeoStatus("Audio failed to load. Check your connection, then tap ▶.");
      updatePlayButton();
    });

    document.getElementById("reset-progress")?.addEventListener("click", () => {
      localStorage.removeItem(STORAGE_KEY);
      state.unlocked = new Set([TOUR.stops[0].id]);
      state.done = new Set();
      state.activeId = TOUR.stops[0].id;
      selectStop(state.activeId);
      renderStopList();
      refreshMarkers();
      setGeoStatus("Progress reset.");
    });
  }

  function init() {
    loadProgress();
    // Always keep stop 1 unlocked
    state.unlocked.add(TOUR.stops[0].id);
    initMap();
    bindEvents();
    selectStop(state.activeId);
    // Do not prompt for GPS on load — the permission dialog blocks taps on “I’m here”.
    // User opts in via Locate me.
    setGeoStatus("Tap Locate me for GPS, or select a stop and tap I’m here.");
    // Open script by default so written narration is primary (placeholder audio)
    state.scriptOpen = true;
    els.scriptDrawer.classList.add("is-open");
    els.scriptToggle.textContent = "Hide script";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
