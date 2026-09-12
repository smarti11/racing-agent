(() => {
  const video = document.getElementById("camera");
  const canvas = document.getElementById("overlay");
  const ctx = canvas.getContext("2d");
  const statusEl = document.getElementById("status");
  const btnStart = document.getElementById("btn-start");
  const liveControls = document.getElementById("live-controls");
  const btnColor = document.getElementById("btn-color");
  const btnThick = document.getElementById("btn-thick");
  const btnLink = document.getElementById("btn-link");
  const btnRotCcw = document.getElementById("btn-rot-ccw");
  const btnRotCw = document.getElementById("btn-rot-cw");
  const btnRotReset = document.getElementById("btn-rot-reset");
  const help = document.getElementById("help");
  const btnHelp = document.getElementById("btn-help");
  const btnCloseHelp = document.getElementById("btn-close-help");
  const markerL = document.getElementById("marker-l");
  const markerR = document.getElementById("marker-r");
  const labelAim = document.getElementById("label-aim");
  const markersLayer = document.getElementById("markers");
  const appEl = document.getElementById("app");

  const COLORS = [
    { id: "lime", value: "#c8f542", glow: "rgba(200, 245, 66, 0.35)" },
    { id: "white", value: "#ffffff", glow: "rgba(255, 255, 255, 0.3)" },
    { id: "yellow", value: "#ffe566", glow: "rgba(255, 229, 102, 0.35)" },
    { id: "black", value: "#111111", glow: "rgba(0, 0, 0, 0.35)" },
  ];

  const EDGE_PAD = 36;
  const MIN_GAP_FRAC = 0.1;
  const ROT_STEP = (5 * Math.PI) / 180;

  let colorIndex = 0;
  let thick = true;
  let equalLock = true;
  let stream = null;
  let raf = 0;

  // Marker-line angle around screen Z (0 = horizontal). AIM stays perpendicular.
  let angle = 0;
  let leftFrac = 0.42;
  let rightFrac = 0.42;

  function setStatus(msg, isError = false) {
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
    if (Math.abs(deg) < 1) return "level";
    return `${deg > 0 ? "+" : ""}${deg}°`;
  }

  function statusHint() {
    const diff = Math.abs(leftFrac - rightFrac);
    if (!equalLock && diff > 0.02) {
      return `Rotated ${angleLabel()} · L/R unequal — turn Equal lock on`;
    }
    return `Rotated ${angleLabel()} · drag L/R · Rotate or two-finger twist`;
  }

  function positionHandles() {
    const l = markerPos("l");
    const r = markerPos("r");
    const deg = (angle * 180) / Math.PI;

    markerL.style.left = `${l.x}px`;
    markerL.style.top = `${l.y}px`;
    markerR.style.left = `${r.x}px`;
    markerR.style.top = `${r.y}px`;

    const c = center();
    const fx = Math.sin(angle);
    const fy = -Math.cos(angle);
    const labelDist = Math.min(window.innerHeight, window.innerWidth) * 0.22;
    labelAim.style.left = `${c.x + fx * labelDist}px`;
    labelAim.style.top = `${c.y + fy * labelDist}px`;
    labelAim.style.transform = `translate(-50%, -50%) rotate(${deg}deg)`;
  }

  function resizeCanvas() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = window.innerWidth;
    const h = window.innerHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    leftFrac = clampFrac(leftFrac);
    rightFrac = clampFrac(rightFrac);
    positionHandles();
  }

  function drawOverlay() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    const c = center();
    const color = COLORS[colorIndex];
    const lineW = thick ? 4 : 2;
    const dash = thick ? [14, 10] : [10, 8];
    const md = markerDir();
    const ad = aimDir();
    const reach = Math.hypot(w, h);
    const l = markerPos("l");
    const r = markerPos("r");

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
    vignette.addColorStop(1, "rgba(0,0,0,0.28)");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, w, h);

    ctx.save();
    ctx.strokeStyle = color.value;
    ctx.fillStyle = color.value;
    ctx.lineWidth = lineW;
    ctx.shadowColor = color.glow;
    ctx.shadowBlur = thick ? 10 : 6;

    ctx.beginPath();
    ctx.setLineDash([]);
    ctx.moveTo(c.x - ad.x * reach, c.y - ad.y * reach);
    ctx.lineTo(c.x + ad.x * reach, c.y + ad.y * reach);
    ctx.stroke();

    ctx.beginPath();
    ctx.setLineDash(dash);
    ctx.moveTo(c.x - md.x * reach, c.y - md.y * reach);
    ctx.lineTo(c.x + md.x * reach, c.y + md.y * reach);
    ctx.stroke();
    ctx.setLineDash([]);

    const box = thick ? 28 : 22;
    ctx.strokeRect(c.x - box / 2, c.y - box / 2, box, box);

    ctx.globalAlpha = 0.4;
    ctx.beginPath();
    ctx.moveTo(l.x, l.y);
    ctx.lineTo(r.x, r.y);
    ctx.stroke();
    ctx.globalAlpha = 1;

    ctx.lineWidth = Math.max(2, lineW - 1);
    const tick = 34;
    for (const p of [l, r]) {
      ctx.beginPath();
      ctx.moveTo(p.x - ad.x * tick, p.y - ad.y * tick);
      ctx.lineTo(p.x + ad.x * tick, p.y + ad.y * tick);
      ctx.stroke();
    }

    const fx = Math.sin(angle);
    const fy = -Math.cos(angle);
    const tip = 56;
    const base = 74;
    const tx = c.x + fx * tip;
    const ty = c.y + fy * tip;
    const bx = c.x + fx * base;
    const by = c.y + fy * base;
    const px = -fy;
    const py = fx;
    ctx.beginPath();
    ctx.moveTo(tx, ty);
    ctx.lineTo(bx + px * 10, by + py * 10);
    ctx.lineTo(bx - px * 10, by - py * 10);
    ctx.closePath();
    ctx.fill();

    ctx.restore();
    raf = requestAnimationFrame(drawOverlay);
  }

  function projectOntoMarkerAxis(clientX, clientY) {
    const c = center();
    const d = markerDir();
    return (clientX - c.x) * d.x + (clientY - c.y) * d.y;
  }

  function bindDrag(el, side) {
    let dragging = false;
    let pointerId = null;

    el.addEventListener("pointerdown", (e) => {
      if (!help.hidden) return;
      dragging = true;
      pointerId = e.pointerId;
      el.classList.add("is-dragging");
      el.setPointerCapture(pointerId);
      e.preventDefault();
      e.stopPropagation();
    });

    el.addEventListener("pointermove", (e) => {
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
      if (!statusEl.classList.contains("error")) setStatus(statusHint());
      e.preventDefault();
    });

    const endDrag = (e) => {
      if (!dragging || e.pointerId !== pointerId) return;
      dragging = false;
      el.classList.remove("is-dragging");
      try {
        el.releasePointerCapture(pointerId);
      } catch (_) {
        /* ignore */
      }
      pointerId = null;
      if (!statusEl.classList.contains("error")) setStatus(statusHint());
    };

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
    if (e.target.closest(".marker-handle, button, .help-sheet, .controls, .top-bar")) return;
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (activePointers.size === 2) {
      const pts = [...activePointers.values()];
      pinchAngle0 = pairAngle(pts[0], pts[1]);
      angleAtPinchStart = angle;
    }
  }

  function onPinchMove(e) {
    if (!activePointers.has(e.pointerId)) return;
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (activePointers.size === 2 && pinchAngle0 != null) {
      const pts = [...activePointers.values()];
      angle = angleAtPinchStart + (pairAngle(pts[0], pts[1]) - pinchAngle0);
      positionHandles();
      if (!statusEl.classList.contains("error")) setStatus(statusHint());
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
    angle += delta;
    positionHandles();
    if (!statusEl.classList.contains("error")) setStatus(statusHint());
  }

  function resetAngle() {
    angle = 0;
    positionHandles();
    if (!statusEl.classList.contains("error")) setStatus(statusHint());
  }

  async function startCamera() {
    if (!window.isSecureContext) {
      setStatus("Camera needs HTTPS (or localhost). Open this page over a secure link.", true);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("This browser cannot access the camera.", true);
      return;
    }

    btnStart.disabled = true;
    setStatus("Starting rear camera…");

    try {
      if (stream) stream.getTracks().forEach((t) => t.stop());

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
      setStatus(statusHint());
      cancelAnimationFrame(raf);
      drawOverlay();
    } catch (err) {
      console.error(err);
      btnStart.disabled = false;
      const name = err && err.name;
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setStatus("Camera permission blocked. Enable it in Safari settings for this site.", true);
      } else if (name === "NotFoundError") {
        setStatus("No camera found on this device.", true);
      } else {
        setStatus("Could not start camera. Try Safari on iPhone.", true);
      }
    }
  }

  function cycleColor() {
    colorIndex = (colorIndex + 1) % COLORS.length;
    btnColor.textContent = `Line: ${COLORS[colorIndex].id}`;
    applyLineColor();
  }

  function toggleThickness() {
    thick = !thick;
    btnThick.textContent = thick ? "Thick lines" : "Thin lines";
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
    setStatus(statusHint());
  }

  function openHelp() {
    help.hidden = false;
  }

  function closeHelp() {
    help.hidden = true;
    try {
      localStorage.setItem("teeAlignHelpSeen", "1");
    } catch (_) {
      /* ignore */
    }
  }

  bindDrag(markerL, "l");
  bindDrag(markerR, "r");
  applyLineColor();

  const rotateRow = document.createElement("div");
  rotateRow.className = "control-row rotate-always";
  rotateRow.append(btnRotCcw, btnRotCw, btnRotReset);
  btnStart.insertAdjacentElement("afterend", rotateRow);

  btnStart.addEventListener("click", startCamera);
  btnColor.addEventListener("click", cycleColor);
  btnThick.addEventListener("click", toggleThickness);
  btnLink.addEventListener("click", toggleEqualLock);
  btnRotCcw.addEventListener("click", () => nudgeAngle(-ROT_STEP));
  btnRotCw.addEventListener("click", () => nudgeAngle(ROT_STEP));
  btnRotReset.addEventListener("click", resetAngle);
  btnHelp.addEventListener("click", openHelp);
  btnCloseHelp.addEventListener("click", closeHelp);

  window.addEventListener("resize", resizeCanvas);
  window.addEventListener("orientationchange", () => setTimeout(resizeCanvas, 250));

  resizeCanvas();
  drawOverlay();
  setStatus("Rotate tee-face line · drag L/R · Enable camera for live view");

  try {
    if (!localStorage.getItem("teeAlignHelpSeen")) openHelp();
  } catch (_) {
    openHelp();
  }

  let wakeLock = null;
  async function requestWakeLock() {
    try {
      if ("wakeLock" in navigator) {
        wakeLock = await navigator.wakeLock.request("screen");
      }
    } catch (_) {
      /* ignore */
    }
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && stream) requestWakeLock();
  });
  btnStart.addEventListener("click", requestWakeLock);
})();
