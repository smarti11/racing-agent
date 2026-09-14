(() => {
  const video = document.getElementById("camera");
  const freezeCanvas = document.getElementById("freeze");
  const freezeCtx = freezeCanvas.getContext("2d");
  const canvas = document.getElementById("overlay");
  const ctx = canvas.getContext("2d");

  const statusEl = document.getElementById("status");
  const btnStart = document.getElementById("btn-start");
  const liveControls = document.getElementById("live-controls");
  const actionControls = document.getElementById("action-controls");
  const btnColor = document.getElementById("btn-color");
  const btnLink = document.getElementById("btn-link");
  const btnSun = document.getElementById("btn-sun");
  const btnResetAngle = document.getElementById("btn-reset-angle");
  const btnRotCcw = document.getElementById("btn-rot-ccw");
  const btnRotCw = document.getElementById("btn-rot-cw");
  const btnSnapLevel = document.getElementById("btn-snap-level");
  const btnFreeze = document.getElementById("btn-freeze");
  const btnPhoto = document.getElementById("btn-photo");
  const help = document.getElementById("help");
  const btnHelp = document.getElementById("btn-help");
  const btnCloseHelp = document.getElementById("btn-close-help");
  const markerL = document.getElementById("marker-l");
  const markerR = document.getElementById("marker-r");
  const labelAim = document.getElementById("label-aim");
  const spacingBadge = document.getElementById("spacing-badge");
  const levelBubble = document.getElementById("level-bubble");
  const levelText = document.getElementById("level-text");
  const levelWell = document.getElementById("level-well");
  const markersLayer = document.getElementById("markers");
  const appEl = document.getElementById("app");

  const COLORS = [
    { id: "lime", value: "#c8f542", glow: "rgba(200, 245, 66, 0.35)" },
    { id: "white", value: "#ffffff", glow: "rgba(255, 255, 255, 0.35)" },
    { id: "yellow", value: "#ffe566", glow: "rgba(255, 229, 102, 0.4)" },
    { id: "black", value: "#111111", glow: "rgba(0, 0, 0, 0.4)" },
  ];

  const EDGE_PAD = 36;
  const MIN_GAP_FRAC = 0.1;
  const ROT_STEP = (5 * Math.PI) / 180;
  const LEVEL_OK_DEG = 2.5;

  let colorIndex = 0;
  let equalLock = true;
  let sunMode = false;
  let frozen = false;
  let stream = null;
  let raf = 0;
  let angle = 0;
  let leftFrac = 0.42;
  let rightFrac = 0.42;
  let phoneRollDeg = 0;
  let phonePitchDeg = 0;
  let orientationReady = false;

  function setStatus(msg, isError) {
    statusEl.textContent = msg || "";
    statusEl.classList.toggle("error", Boolean(isError));
  }

  function applyLineColor() {
    const c = COLORS[colorIndex];
    document.documentElement.style.setProperty("--line", c.value);
    document.documentElement.style.setProperty("--line-glow", c.glow);
  }

  function halfWidth() {
    return Math.max(1, window.innerWidth / 2);
  }

  function clampFrac(frac) {
    const maxFrac = Math.max(0.12, (halfWidth() - EDGE_PAD) / halfWidth());
    return Math.min(maxFrac, Math.max(MIN_GAP_FRAC, frac));
  }

  function center() {
    return { x: window.innerWidth / 2, y: window.innerHeight / 2 };
  }

  function markerDir() {
    return { x: Math.cos(angle), y: Math.sin(angle) };
  }

  function aimDir() {
    return { x: -Math.sin(angle), y: Math.cos(angle) };
  }

  function markerPos(side) {
    const c = center();
    const d = markerDir();
    const hw = halfWidth();
    const dist = (side === "l" ? -leftFrac : rightFrac) * hw;
    return { x: c.x + d.x * dist, y: c.y + d.y * dist };
  }

  function angleLabel() {
    let deg = Math.round((angle * 180) / Math.PI);
    deg = ((((deg + 180) % 360) + 360) % 360) - 180;
    if (Math.abs(deg) < 1) return "0°";
    return (deg > 0 ? "+" : "") + deg + "°";
  }

  function spacingInfo() {
    const diff = Math.abs(leftFrac - rightFrac);
    const equal = equalLock || diff <= 0.02;
    if (equal) {
      const mid = Math.round(((leftFrac + rightFrac) / 2) * 100);
      return { text: "EQUAL · " + mid + "% width", equal: true };
    }
    return {
      text: "UNEVEN · L" + Math.round(leftFrac * 100) + "% R" + Math.round(rightFrac * 100) + "%",
      equal: false,
    };
  }

  function updateSpacingBadge() {
    const s = spacingInfo();
    spacingBadge.textContent = s.text;
    spacingBadge.classList.toggle("is-equal", s.equal);
    spacingBadge.classList.toggle("is-uneven", !s.equal);
  }

  function refreshHud() {
    updateSpacingBadge();
    if (!statusEl.classList.contains("error")) {
      const s = spacingInfo();
      const freezeBit = frozen ? " · FROZEN" : "";
      let levelBit = "";
      if (orientationReady) {
        const ok = Math.abs(phoneRollDeg) <= LEVEL_OK_DEG && Math.abs(phonePitchDeg) <= 6;
        levelBit = ok ? " · phone level" : " · phone tilt " + Math.round(phoneRollDeg) + "°";
      }
      setStatus("Aim " + angleLabel() + " · " + s.text + freezeBit + levelBit, false);
    }
  }

  function positionHandles() {
    const l = markerPos("l");
    const r = markerPos("r");
    const deg = (angle * 180) / Math.PI;
    markerL.style.left = l.x + "px";
    markerL.style.top = l.y + "px";
    markerR.style.left = r.x + "px";
    markerR.style.top = r.y + "px";

    const c = center();
    const fx = Math.sin(angle);
    const fy = -Math.cos(angle);
    const labelDist = Math.min(window.innerHeight, window.innerWidth) * 0.22;
    labelAim.style.left = c.x + fx * labelDist + "px";
    labelAim.style.top = c.y + fy * labelDist + "px";
    labelAim.style.transform = "translate(-50%, -50%) rotate(" + deg + "deg)";
    updateSpacingBadge();
  }

  function resizeCanvases() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = window.innerWidth;
    const h = window.innerHeight;
    [canvas, freezeCanvas].forEach(function (c) {
      c.width = Math.floor(w * dpr);
      c.height = Math.floor(h * dpr);
      c.style.width = w + "px";
      c.style.height = h + "px";
    });
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    freezeCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    leftFrac = clampFrac(leftFrac);
    rightFrac = clampFrac(rightFrac);
    positionHandles();
    if (frozen) captureFreezeFrame();
  }

  function strokeWidth() {
    return sunMode ? 7 : 4;
  }

  function drawGuideLines(g, w, h) {
    const c = center();
    const color = COLORS[colorIndex];
    const lineW = strokeWidth();
    const dash = sunMode ? [18, 12] : [14, 10];
    const md = markerDir();
    const ad = aimDir();
    const reach = Math.hypot(w, h);
    const l = markerPos("l");
    const r = markerPos("r");

    g.save();

    if (sunMode) {
      g.strokeStyle = "#000";
      g.lineWidth = lineW + 4;
      g.beginPath();
      g.setLineDash([]);
      g.moveTo(c.x - ad.x * reach, c.y - ad.y * reach);
      g.lineTo(c.x + ad.x * reach, c.y + ad.y * reach);
      g.stroke();
      g.beginPath();
      g.setLineDash(dash);
      g.moveTo(c.x - md.x * reach, c.y - md.y * reach);
      g.lineTo(c.x + md.x * reach, c.y + md.y * reach);
      g.stroke();
      g.setLineDash([]);
    }

    g.strokeStyle = color.value;
    g.fillStyle = color.value;
    g.lineWidth = lineW;
    g.shadowColor = color.glow;
    g.shadowBlur = sunMode ? 14 : 8;

    g.beginPath();
    g.setLineDash([]);
    g.moveTo(c.x - ad.x * reach, c.y - ad.y * reach);
    g.lineTo(c.x + ad.x * reach, c.y + ad.y * reach);
    g.stroke();

    g.beginPath();
    g.setLineDash(dash);
    g.moveTo(c.x - md.x * reach, c.y - md.y * reach);
    g.lineTo(c.x + md.x * reach, c.y + md.y * reach);
    g.stroke();
    g.setLineDash([]);

    const box = sunMode ? 34 : 28;
    g.strokeRect(c.x - box / 2, c.y - box / 2, box, box);

    g.globalAlpha = 0.45;
    g.beginPath();
    g.moveTo(l.x, l.y);
    g.lineTo(r.x, r.y);
    g.stroke();
    g.globalAlpha = 1;

    g.lineWidth = Math.max(2, lineW - 1);
    const tick = sunMode ? 42 : 34;
    [l, r].forEach(function (p) {
      g.beginPath();
      g.moveTo(p.x - ad.x * tick, p.y - ad.y * tick);
      g.lineTo(p.x + ad.x * tick, p.y + ad.y * tick);
      g.stroke();
    });

    const fx = Math.sin(angle);
    const fy = -Math.cos(angle);
    const tip = 78;
    const base = 58;
    const tx = c.x + fx * tip;
    const ty = c.y + fy * tip;
    const bx = c.x + fx * base;
    const by = c.y + fy * base;
    const px = -fy;
    const py = fx;
    g.beginPath();
    g.moveTo(tx, ty);
    g.lineTo(bx + px * 10, by + py * 10);
    g.lineTo(bx - px * 10, by - py * 10);
    g.closePath();
    g.fill();

    g.restore();
  }

  function drawOverlay() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    const c = center();
    ctx.clearRect(0, 0, w, h);

    const vignette = ctx.createRadialGradient(
      c.x,
      c.y,
      Math.min(w, h) * 0.2,
      c.x,
      c.y,
      Math.max(w, h) * 0.75
    );
    vignette.addColorStop(0, "rgba(0,0,0,0)");
    vignette.addColorStop(1, sunMode ? "rgba(0,0,0,0.38)" : "rgba(0,0,0,0.28)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, w, h);

    drawGuideLines(ctx, w, h);
    raf = requestAnimationFrame(drawOverlay);
  }

  function captureFreezeFrame() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    freezeCtx.fillStyle = "#000";
    freezeCtx.fillRect(0, 0, w, h);
    try {
      const vw = video.videoWidth || w;
      const vh = video.videoHeight || h;
      const scale = Math.max(w / vw, h / vh);
      const dw = vw * scale;
      const dh = vh * scale;
      freezeCtx.drawImage(video, (w - dw) / 2, (h - dh) / 2, dw, dh);
    } catch (e) {
      /* ignore */
    }
  }

  function setFrozen(next) {
    if (next && !stream) {
      setStatus("Enable the camera before freezing.", true);
      return;
    }
    frozen = next;
    btnFreeze.textContent = frozen ? "Live" : "Freeze";
    btnFreeze.setAttribute("aria-pressed", frozen ? "true" : "false");
    document.body.classList.toggle("is-frozen", frozen);
    freezeCanvas.hidden = !frozen;
    if (frozen) {
      captureFreezeFrame();
      try {
        video.pause();
      } catch (e) {
        /* ignore */
      }
    } else {
      video.play().catch(function () {});
    }
    refreshHud();
  }

  function projectOntoMarkerAxis(clientX, clientY) {
    const c = center();
    const d = markerDir();
    return (clientX - c.x) * d.x + (clientY - c.y) * d.y;
  }

  function bindDrag(el, side) {
    let dragging = false;
    let pointerId = null;

    el.addEventListener("pointerdown", function (e) {
      if (!help.hidden || frozen) return;
      dragging = true;
      pointerId = e.pointerId;
      el.classList.add("is-dragging");
      el.setPointerCapture(pointerId);
      e.preventDefault();
      e.stopPropagation();
    });

    el.addEventListener("pointermove", function (e) {
      if (!dragging || e.pointerId !== pointerId) return;
      const hw = halfWidth();
      let along = projectOntoMarkerAxis(e.clientX, e.clientY);
      if (side === "l") {
        along = Math.min(-MIN_GAP_FRAC * hw, Math.max(-(hw - EDGE_PAD), along));
        leftFrac = clampFrac(-along / hw);
        if (equalLock) rightFrac = leftFrac;
      } else {
        along = Math.max(MIN_GAP_FRAC * hw, Math.min(hw - EDGE_PAD, along));
        rightFrac = clampFrac(along / hw);
        if (equalLock) leftFrac = rightFrac;
      }
      positionHandles();
      refreshHud();
      e.preventDefault();
    });

    function endDrag(e) {
      if (!dragging || e.pointerId !== pointerId) return;
      dragging = false;
      el.classList.remove("is-dragging");
      try {
        el.releasePointerCapture(pointerId);
      } catch (err) {
        /* ignore */
      }
      pointerId = null;
      refreshHud();
    }

    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
  }

  const activePointers = new Map();
  let pinchAngle0 = null;
  let angleAtPinchStart = 0;

  function pairAngle(a, b) {
    return Math.atan2(b.y - a.y, b.x - a.x);
  }

  function onPinchDown(e) {
    if (frozen) return;
    if (e.target.closest(".marker-handle, button, .help-sheet, .controls, .top-bar")) return;
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (activePointers.size === 2) {
      const pts = Array.from(activePointers.values());
      pinchAngle0 = pairAngle(pts[0], pts[1]);
      angleAtPinchStart = angle;
    }
  }

  function onPinchMove(e) {
    if (!activePointers.has(e.pointerId) || frozen) return;
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (activePointers.size === 2 && pinchAngle0 != null) {
      const pts = Array.from(activePointers.values());
      angle = angleAtPinchStart + (pairAngle(pts[0], pts[1]) - pinchAngle0);
      positionHandles();
      refreshHud();
    }
  }

  function onPinchEnd(e) {
    activePointers.delete(e.pointerId);
    if (activePointers.size < 2) pinchAngle0 = null;
  }

  markersLayer.addEventListener("pointerdown", onPinchDown);
  markersLayer.addEventListener("pointermove", onPinchMove);
  markersLayer.addEventListener("pointerup", onPinchEnd);
  markersLayer.addEventListener("pointercancel", onPinchEnd);
  appEl.addEventListener("pointerdown", onPinchDown);
  appEl.addEventListener("pointermove", onPinchMove);
  appEl.addEventListener("pointerup", onPinchEnd);
  appEl.addEventListener("pointercancel", onPinchEnd);

  function nudgeAngle(delta) {
    if (frozen) return;
    angle += delta;
    positionHandles();
    refreshHud();
  }

  function resetAngle() {
    if (frozen) return;
    angle = 0;
    positionHandles();
    refreshHud();
  }

  function updateLevelMeter() {
    const span = 12;
    const x = Math.max(-1, Math.min(1, phoneRollDeg / span));
    const y = Math.max(-1, Math.min(1, phonePitchDeg / span));
    levelBubble.style.left = 50 + x * 34 + "%";
    levelBubble.style.top = 50 + y * 34 + "%";
    const isLevel =
      orientationReady &&
      Math.abs(phoneRollDeg) <= LEVEL_OK_DEG &&
      Math.abs(phonePitchDeg) <= 6;
    levelWell.classList.toggle("is-level", isLevel);
    if (!orientationReady) levelText.textContent = "Level —";
    else if (isLevel) levelText.textContent = "Level OK";
    else levelText.textContent = "Tilt " + Math.round(phoneRollDeg) + "°";
  }

  let levelTick = 0;
  function onOrientation(e) {
    if (e.gamma == null || e.beta == null) return;
    orientationReady = true;
    phoneRollDeg = e.gamma;
    phonePitchDeg = e.beta - 90;
    updateLevelMeter();
    levelTick = (levelTick + 1) % 10;
    if (levelTick === 0 && !statusEl.classList.contains("error")) refreshHud();
  }

  async function ensureOrientationPermission() {
    try {
      if (
        typeof DeviceOrientationEvent !== "undefined" &&
        typeof DeviceOrientationEvent.requestPermission === "function"
      ) {
        const res = await DeviceOrientationEvent.requestPermission();
        if (res === "granted") {
          window.addEventListener("deviceorientation", onOrientation, true);
          return true;
        }
        return false;
      }
      window.addEventListener("deviceorientation", onOrientation, true);
      return true;
    } catch (e) {
      return false;
    }
  }

  function snapToGravityLevel() {
    if (frozen) return;
    if (!orientationReady) {
      setStatus("Move the phone a bit, then tap Snap level again.", true);
      return;
    }
    angle = (-phoneRollDeg * Math.PI) / 180;
    positionHandles();
    setStatus("Snapped to gravity level · " + angleLabel(), false);
    refreshHud();
  }

  async function startCamera() {
    if (!window.isSecureContext) {
      setStatus("Camera needs HTTPS (or localhost).", true);
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("This browser cannot access the camera.", true);
      return;
    }

    btnStart.disabled = true;
    setStatus("Starting rear camera…", false);
    await ensureOrientationPermission();

    try {
      if (stream) stream.getTracks().forEach(function (t) { t.stop(); });

      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      });

      video.srcObject = stream;
      await video.play();

      btnStart.classList.add("hidden");
      liveControls.classList.remove("hidden");
      actionControls.classList.remove("hidden");
      setFrozen(false);
      refreshHud();
      cancelAnimationFrame(raf);
      drawOverlay();
    } catch (err) {
      console.error(err);
      btnStart.disabled = false;
      const name = err && err.name;
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setStatus("Camera permission blocked. Enable it in Safari for this site.", true);
      } else if (name === "NotFoundError") {
        setStatus("No camera found on this device.", true);
      } else {
        setStatus("Could not start camera. Try Safari on iPhone.", true);
      }
    }
  }

  function cycleColor() {
    colorIndex = (colorIndex + 1) % COLORS.length;
    btnColor.textContent = "Line: " + COLORS[colorIndex].id;
    applyLineColor();
  }

  function toggleEqualLock() {
    equalLock = !equalLock;
    btnLink.textContent = equalLock ? "Equal lock: on" : "Equal lock: off";
    btnLink.setAttribute("aria-pressed", equalLock ? "true" : "false");
    if (equalLock) {
      const mid = (leftFrac + rightFrac) / 2;
      leftFrac = clampFrac(mid);
      rightFrac = leftFrac;
      positionHandles();
    }
    refreshHud();
  }

  function toggleSunMode() {
    sunMode = !sunMode;
    document.body.classList.toggle("sun-mode", sunMode);
    btnSun.textContent = sunMode ? "Sun mode: on" : "Sun mode: off";
    btnSun.setAttribute("aria-pressed", sunMode ? "true" : "false");
    refreshHud();
  }

  function savePhoto() {
    if (!stream && !frozen) {
      setStatus("Enable the camera first.", true);
      return;
    }

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = window.innerWidth;
    const h = window.innerHeight;
    const out = document.createElement("canvas");
    out.width = Math.floor(w * dpr);
    out.height = Math.floor(h * dpr);
    const octx = out.getContext("2d");
    octx.setTransform(dpr, 0, 0, dpr, 0, 0);
    octx.fillStyle = "#000";
    octx.fillRect(0, 0, w, h);

    try {
      if (frozen) {
        octx.drawImage(freezeCanvas, 0, 0, freezeCanvas.width, freezeCanvas.height, 0, 0, w, h);
      } else {
        const vw = video.videoWidth || w;
        const vh = video.videoHeight || h;
        const scale = Math.max(w / vw, h / vh);
        const dw = vw * scale;
        const dh = vh * scale;
        octx.drawImage(video, (w - dw) / 2, (h - dh) / 2, dw, dh);
      }
    } catch (e) {
      /* ignore */
    }

    drawGuideLines(octx, w, h);

    const s = spacingInfo();
    octx.fillStyle = "rgba(5,13,9,0.65)";
    octx.fillRect(12, h - 64, w - 24, 48);
    octx.fillStyle = "#f7f4ea";
    octx.font = "600 16px 'Libre Franklin', sans-serif";
    octx.fillText("Tee Align · " + s.text + " · aim " + angleLabel(), 24, h - 34);

    out.toBlob(function (blob) {
      if (!blob) {
        setStatus("Could not create photo.", true);
        return;
      }
      const file = new File([blob], "tee-align-" + Date.now() + ".jpg", { type: "image/jpeg" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], title: "Tee Align" })
          .then(function () { setStatus("Photo shared.", false); })
          .catch(function (err) {
            if (!err || err.name !== "AbortError") downloadBlob(blob, file.name);
          });
        return;
      }
      downloadBlob(blob, file.name);
    }, "image/jpeg", 0.92);
  }

  function downloadBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
    setStatus("Photo saved.", false);
  }

  function openHelp() {
    help.hidden = false;
  }

  function closeHelp() {
    help.hidden = true;
    try {
      localStorage.setItem("teeAlignHelpSeen", "1");
    } catch (e) {
      /* ignore */
    }
  }

  bindDrag(markerL, "l");
  bindDrag(markerR, "r");
  applyLineColor();
  updateLevelMeter();
  updateSpacingBadge();

  btnStart.addEventListener("click", startCamera);
  btnColor.addEventListener("click", cycleColor);
  btnLink.addEventListener("click", toggleEqualLock);
  btnSun.addEventListener("click", toggleSunMode);
  btnResetAngle.addEventListener("click", resetAngle);
  btnRotCcw.addEventListener("click", function () { nudgeAngle(-ROT_STEP); });
  btnRotCw.addEventListener("click", function () { nudgeAngle(ROT_STEP); });
  btnSnapLevel.addEventListener("click", function () {
    ensureOrientationPermission().then(function () { snapToGravityLevel(); });
  });
  btnFreeze.addEventListener("click", function () { setFrozen(!frozen); });
  btnPhoto.addEventListener("click", savePhoto);
  btnHelp.addEventListener("click", openHelp);
  btnCloseHelp.addEventListener("click", closeHelp);

  if (
    typeof DeviceOrientationEvent !== "undefined" &&
    typeof DeviceOrientationEvent.requestPermission !== "function"
  ) {
    window.addEventListener("deviceorientation", onOrientation, true);
  }

  window.addEventListener("resize", resizeCanvases);
  window.addEventListener("orientationchange", function () {
    setTimeout(resizeCanvases, 250);
  });

  resizeCanvases();
  drawOverlay();
  setStatus("Enable camera · Snap level · drag L/R · Freeze to place markers", false);

  try {
    if (!localStorage.getItem("teeAlignHelpSeen")) openHelp();
  } catch (e) {
    openHelp();
  }

  let wakeLock = null;
  async function requestWakeLock() {
    try {
      if ("wakeLock" in navigator) wakeLock = await navigator.wakeLock.request("screen");
    } catch (e) {
      /* ignore */
    }
  }
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && stream) requestWakeLock();
  });
  btnStart.addEventListener("click", requestWakeLock);
})();
