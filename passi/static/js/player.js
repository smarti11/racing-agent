(function () {
  "use strict";

  const params = new URLSearchParams(location.search);
  const token = params.get("token");
  if (!token) {
    location.href = "/static/index.html";
    return;
  }

  let PACK = null;
  let unlockRadius = 90;

  const state = {
    activeId: null,
    unlocked: new Set(),
    done: new Set(),
    watchId: null,
    scriptOpen: true,
  };

  const els = {
    tourTitle: document.getElementById("tour-title"),
    sessionChip: document.getElementById("session-chip"),
    stopList: document.getElementById("stop-list"),
    geoStatus: document.getElementById("geo-status"),
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
    photoGallery: document.getElementById("photo-gallery"),
    lightbox: document.getElementById("lightbox"),
    lightboxImg: document.getElementById("lightbox-img"),
    lightboxCaption: document.getElementById("lightbox-caption"),
    lightboxClose: document.getElementById("lightbox-close"),
  };

  let map;
  let userMarker;
  let accuracyCircle;
  const stopMarkers = new Map();
  let playToken = 0;
  let storageKey = "";

  function stopById(id) {
    return PACK.stops.find((s) => s.id === id);
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

  function loadProgress() {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) return;
      const data = JSON.parse(raw);
      state.unlocked = new Set(data.unlocked || []);
      state.done = new Set(data.done || []);
      if (data.activeId && stopById(data.activeId)) state.activeId = data.activeId;
    } catch (_) {}
  }

  function saveProgress() {
    localStorage.setItem(
      storageKey,
      JSON.stringify({
        unlocked: [...state.unlocked],
        done: [...state.done],
        activeId: state.activeId,
      })
    );
  }

  function pinIcon(stop, kind) {
    return L.divIcon({
      className: "",
      html: `<div class="marker-pin marker-pin--${kind}"><span>${stop.order}</span></div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 28],
    });
  }

  function markerKind(stop) {
    if (stop.id === state.activeId) return "active";
    if (state.done.has(stop.id)) return "done";
    if (state.unlocked.has(stop.id)) return "unlocked";
    return "locked";
  }

  function initMap() {
    map = L.map("map", { zoomControl: false }).setView(PACK.mapCenter, PACK.mapZoom || 14);
    L.control.zoom({ position: "topright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);
    PACK.stops.forEach((stop) => {
      const marker = L.marker([stop.lat, stop.lng], {
        icon: pinIcon(stop, markerKind(stop)),
        title: stop.name,
      }).addTo(map);
      marker.on("click", () => activateStop(stop.id));
      stopMarkers.set(stop.id, marker);
    });
    const bounds = L.latLngBounds(PACK.stops.map((s) => [s.lat, s.lng]));
    map.fitBounds(bounds.pad(0.18));
  }

  function refreshMarkers() {
    PACK.stops.forEach((stop) => {
      const m = stopMarkers.get(stop.id);
      if (m) m.setIcon(pinIcon(stop, markerKind(stop)));
    });
  }

  function renderStopList() {
    els.stopList.innerHTML = "";
    PACK.stops.forEach((stop) => {
      const unlocked = state.unlocked.has(stop.id);
      const done = state.done.has(stop.id);
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "stop-item";
      if (stop.id === state.activeId) btn.classList.add("is-active");
      if (!unlocked) btn.classList.add("is-locked");
      if (unlocked && !done) btn.classList.add("is-unlocked");
      if (done) btn.classList.add("is-done");
      const badge = done ? "Heard" : unlocked ? "Unlocked" : "Locked";
      btn.innerHTML = `
        <span class="stop-num">${stop.order}</span>
        <span class="stop-meta">
          <strong>${stop.name}</strong>
          <small>${stop.walkFromPrev || ""}</small>
        </span>
        <span class="stop-badge">${badge}</span>`;
      btn.addEventListener("click", () => activateStop(stop.id));
      li.appendChild(btn);
      els.stopList.appendChild(li);
    });
  }

  function renderScript(stop) {
    els.scriptBody.innerHTML = "";
    (stop.script || []).forEach((para, i) => {
      const p = document.createElement("p");
      p.dataset.index = String(i);
      p.textContent = para;
      els.scriptBody.appendChild(p);
    });
  }

  function renderPhotos(stop) {
    const photos = stop.photos || [];
    els.photoGallery.innerHTML = "";
    if (!photos.length) {
      els.photoGallery.hidden = true;
      return;
    }
    els.photoGallery.hidden = false;
    photos.forEach((photo) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "photo-card";
      btn.innerHTML = `<img src="${photo.url}" alt="${photo.caption || stop.name}" loading="lazy" /><figcaption>${photo.caption || ""}</figcaption>`;
      btn.addEventListener("click", () => {
        els.lightboxImg.src = photo.url;
        els.lightboxImg.alt = photo.caption || "";
        els.lightboxCaption.textContent = photo.caption || "";
        els.lightbox.hidden = false;
      });
      els.photoGallery.appendChild(btn);
    });
  }

  function highlightScript(progress) {
    const paras = els.scriptBody.querySelectorAll("p");
    if (!paras.length) return;
    const idx = Math.min(paras.length - 1, Math.floor(progress * paras.length));
    paras.forEach((p, i) => p.classList.toggle("is-current", i === idx));
  }

  function needsAudioRefresh() {
    return !!(PACK && PACK.stops && PACK.stops.some((s) => !s.audioUrl));
  }

  async function refreshPackAudio() {
    try {
      const res = await fetch(`/api/sessions/${token}`, { cache: "no-store" });
      if (!res.ok) return false;
      const data = await res.json();
      const fresh = data.pack;
      if (!fresh || !fresh.stops || !PACK) return false;
      let gained = 0;
      fresh.stops.forEach((fs) => {
        const local = stopById(fs.id);
        if (!local) return;
        if (fs.audioUrl && local.audioUrl !== fs.audioUrl) {
          local.audioUrl = fs.audioUrl;
          local.durationSec = fs.durationSec || local.durationSec || 0;
          gained += 1;
        }
      });
      if (gained && state.activeId) {
        const active = activeStop();
        if (active && active.audioUrl && els.audio.dataset.stopId !== active.id) {
          selectStop(active.id, { pan: false, autoplay: false });
        }
      }
      return gained > 0;
    } catch (_) {
      return false;
    }
  }

  function startAudioPolling() {
    if (!needsAudioRefresh()) return;
    let tries = 0;
    const maxTries = 36; // ~3 minutes at 5s
    const timer = setInterval(async () => {
      tries += 1;
      const gained = await refreshPackAudio();
      if (gained && state.activeId) {
        const stop = activeStop();
        if (stop && state.unlocked.has(stop.id) && stop.audioUrl) {
          els.playerSub.textContent = "Tap ▶ or the stop number to hear the guide";
        }
      }
      if (!needsAudioRefresh() || tries >= maxTries) clearInterval(timer);
    }, 5000);
  }

  function selectStop(id, opts = {}) {
    const stop = stopById(id);
    if (!stop) return;
    const unlocked = state.unlocked.has(id);
    state.activeId = id;
    saveProgress();
    els.playerTitle.textContent = `${stop.order}. ${stop.name}`;
    els.playerSub.textContent = unlocked
      ? stop.audioUrl
        ? "Tap ▶ or the stop number to hear the guide"
        : "Preparing audio… tap ▶ in a moment (script is ready now)"
      : "Locked — tap the stop to unlock & play";
    els.walkCue.textContent = stop.walkFromPrev || "";
    renderScript(stop);
    renderPhotos(stop);
    highlightScript(0);
    els.playBtn.disabled = !unlocked;
    els.scrub.disabled = !unlocked;
    els.markDoneBtn.disabled = !unlocked;
    els.imHereBtn.disabled = unlocked;

    const switching = els.audio.dataset.stopId && els.audio.dataset.stopId !== stop.id;
    if (switching && !els.audio.paused) els.audio.pause();

    if (unlocked && stop.audioUrl) {
      if (els.audio.dataset.stopId !== stop.id) {
        els.audio.src = stop.audioUrl;
        els.audio.dataset.stopId = stop.id;
        els.audio.load();
        els.timeDur.textContent = formatTime(stop.durationSec || 0);
        els.scrub.value = 0;
        els.timeCur.textContent = "0:00";
      }
    } else {
      els.audio.removeAttribute("src");
      els.audio.dataset.stopId = "";
      els.timeDur.textContent = formatTime(stop.durationSec || 0);
      if (unlocked && !stop.audioUrl) refreshPackAudio();
    }
    renderStopList();
    refreshMarkers();
    if (opts.pan !== false && map) map.panTo([stop.lat, stop.lng], { animate: true });
    if (opts.autoplay && unlocked) {
      // Ensure late-arriving background TTS is merged before attempting play.
      if (!stop.audioUrl) {
        refreshPackAudio().then(() => playCurrent());
      } else {
        playCurrent();
      }
    }
  }

  function activateStop(id) {
    if (!state.unlocked.has(id)) {
      state.unlocked.add(id);
      saveProgress();
      setGeoStatus(`Unlocked: ${stopById(id).shortName} (tapped)`);
    }
    selectStop(id, { autoplay: true });
  }

  async function advanceToNextStop({ autoplay = false } = {}) {
    const stop = activeStop();
    if (!stop || !state.unlocked.has(stop.id)) return;
    state.done.add(stop.id);
    const next = PACK.stops.find((s) => s.order === stop.order + 1);
    saveProgress();
    if (!next) {
      els.playerSub.textContent = "Tour complete — thanks for walking with Passi";
      renderStopList();
      refreshMarkers();
      return;
    }
    state.unlocked.add(next.id);
    saveProgress();
    if (!next.audioUrl) await refreshPackAudio();
    selectStop(next.id, { autoplay });
    if (!autoplay) {
      els.playerSub.textContent = next.audioUrl
        ? `Next: ${next.shortName} — tap ▶ to play`
        : `Next: ${next.shortName} — preparing audio…`;
    }
  }

  async function playCurrent() {
    let stop = activeStop();
    if (!stop || !state.unlocked.has(stop.id)) return;
    if (!stop.audioUrl) {
      els.playerSub.textContent = "Preparing audio…";
      await refreshPackAudio();
      stop = activeStop();
      if (!stop || !stop.audioUrl) {
        els.playerSub.textContent = "Audio still preparing — try ▶ again in a few seconds";
        return;
      }
      // Bind the newly arrived URL without recursing autoplay.
      if (els.audio.dataset.stopId !== stop.id) {
        els.audio.src = stop.audioUrl;
        els.audio.dataset.stopId = stop.id;
        els.audio.load();
        els.timeDur.textContent = formatTime(stop.durationSec || 0);
      }
    }
    const tokenN = ++playToken;
    if (els.audio.dataset.stopId !== stop.id || !els.audio.getAttribute("src") || els.audio.error) {
      els.audio.src = stop.audioUrl;
      els.audio.dataset.stopId = stop.id;
      els.audio.load();
    }
    els.audio.volume = 1;
    const tryPlay = () => {
      if (tokenN !== playToken) return;
      els.audio
        .play()
        .then(() => {
          if (tokenN !== playToken) return;
          els.playerSub.textContent = "Playing — read along with the script";
          updatePlayButton();
        })
        .catch(() => {
          els.playerSub.textContent = "Tap ▶ to start audio";
          updatePlayButton();
        });
    };
    if (els.audio.readyState >= 2) tryPlay();
    else {
      els.audio.addEventListener("canplay", tryPlay, { once: true });
      setTimeout(tryPlay, 400);
    }
  }

  function updatePlayButton() {
    const playing = els.audio && !els.audio.paused && !els.audio.ended;
    els.playBtn.textContent = playing ? "❚❚" : "▶";
  }

  function setGeoStatus(msg) {
    els.geoStatus.textContent = msg;
  }

  function checkProximity(lat, lng) {
    PACK.stops.forEach((stop) => {
      if (state.unlocked.has(stop.id)) return;
      const d = haversineMeters(lat, lng, stop.lat, stop.lng);
      if (d <= unlockRadius) {
        state.unlocked.add(stop.id);
        saveProgress();
        setGeoStatus(`Unlocked: ${stop.shortName} (${Math.round(d)} m)`);
        if (state.activeId === stop.id) selectStop(stop.id, { pan: false });
        else {
          renderStopList();
          refreshMarkers();
        }
      }
    });
  }

  function updateUserLocation(lat, lng, accuracy) {
    checkProximity(lat, lng);
    const latlng = L.latLng(lat, lng);
    if (!userMarker) {
      userMarker = L.marker(latlng, {
        icon: L.divIcon({
          className: "",
          html: '<div class="user-dot"></div>',
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

  function startWatching() {
    if (!navigator.geolocation || state.watchId != null) return;
    state.watchId = navigator.geolocation.watchPosition(
      (pos) => {
        updateUserLocation(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
        setGeoStatus(`GPS on · ±${Math.round(pos.coords.accuracy || 0)} m`);
      },
      () => setGeoStatus("Location error — tap a stop or I’m here."),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
  }

  function bindEvents() {
    els.playBtn.addEventListener("click", () => {
      const stop = activeStop();
      if (!stop || !state.unlocked.has(stop.id)) {
        if (stop) activateStop(stop.id);
        return;
      }
      if (els.audio.paused || els.audio.ended) playCurrent();
      else {
        els.audio.pause();
        els.playerSub.textContent = "Paused";
        updatePlayButton();
      }
    });
    els.imHereBtn.addEventListener("click", () => {
      if (state.activeId) activateStop(state.activeId);
    });
    els.locateBtn.addEventListener("click", () => {
      if (!navigator.geolocation) return setGeoStatus("GPS unavailable");
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          updateUserLocation(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
          map.setView([pos.coords.latitude, pos.coords.longitude], Math.max(map.getZoom(), 16));
          startWatching();
        },
        () => setGeoStatus("Could not get a fix — tap a stop instead.")
      );
    });
    els.scriptToggle.addEventListener("click", () => {
      state.scriptOpen = !state.scriptOpen;
      els.scriptDrawer.classList.toggle("is-open", state.scriptOpen);
      els.scriptToggle.textContent = state.scriptOpen ? "Hide script" : "Show script";
    });
    els.markDoneBtn.addEventListener("click", () => {
      advanceToNextStop({ autoplay: false });
    });
    els.scrub.addEventListener("input", () => {
      if (!els.audio.duration) return;
      els.audio.currentTime = (Number(els.scrub.value) / 100) * els.audio.duration;
    });
    els.audio.addEventListener("timeupdate", () => {
      if (!els.audio.duration) return;
      els.scrub.value = String((els.audio.currentTime / els.audio.duration) * 100);
      els.timeCur.textContent = formatTime(els.audio.currentTime);
      els.timeDur.textContent = formatTime(els.audio.duration);
      highlightScript(els.audio.currentTime / els.audio.duration);
    });
    els.audio.addEventListener("play", updatePlayButton);
    els.audio.addEventListener("pause", updatePlayButton);
    els.audio.addEventListener("ended", () => {
      updatePlayButton();
      // Keep the guided tour moving — unlock + autoplay the next stop.
      advanceToNextStop({ autoplay: true });
    });
    els.lightboxClose.addEventListener("click", () => {
      els.lightbox.hidden = true;
    });
    els.lightbox.addEventListener("click", (e) => {
      if (e.target === els.lightbox) els.lightbox.hidden = true;
    });
  }

  async function boot() {
    const res = await fetch(`/api/sessions/${token}`);
    const data = await res.json();
    if (res.status === 410 || data.expired) {
      location.href = `/static/expired.html?token=${token}`;
      return;
    }
    if (!res.ok) {
      els.playerSub.textContent = data.error || "Session error";
      return;
    }
    PACK = data.pack;
    unlockRadius = PACK.unlockRadiusMeters || 90;
    storageKey = `passi:${token}`;
    els.tourTitle.textContent = PACK.title;
    const exp = new Date(data.session.expiresAt);
    els.sessionChip.textContent = `Expires ${exp.toLocaleString()}`;

    state.unlocked.add(PACK.stops[0].id);
    loadProgress();
    state.unlocked.add(PACK.stops[0].id);
    if (!state.activeId) state.activeId = PACK.stops[0].id;

    initMap();
    bindEvents();
    selectStop(state.activeId);
    startAudioPolling();
    setGeoStatus("Tap Locate me for GPS, or tap a stop number.");
  }

  boot().catch((e) => {
    els.playerSub.textContent = String(e);
  });
})();
