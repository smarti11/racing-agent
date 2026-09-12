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
  const help = document.getElementById("help");
  const btnHelp = document.getElementById("btn-help");
  const btnCloseHelp = document.getElementById("btn-close-help");
  const markerL = document.getElementById("marker-l");
  const markerR = document.getElementById("marker-r");

  const COLORS = [
    { id: "lime", value: "#c8f542", glow: "rgba(200, 245, 66, 0.35)" },
    { id: "white", value: "#ffffff", glow: "rgba(255, 255, 255, 0.3)" },
    { id: "yellow", value: "#ffe566", glow: "rgba(255, 229, 102, 0.35)" },
    { id: "black", value: "#111111", glow: "rgba(0, 0, 0, 0.35)" },
  ];

  const EDGE_PAD = 36;
  const MIN_GAP = 28;

  let colorIndex = 0;
  let thick = true;
  let equalLock = true;
  let stream = null;
  let raf = 0;

  // Distances from screen center as a fraction of half-width (0.15–0.92)
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
    return Math.min(maxFrac, Math.max(0.12, frac));
  }

  function markerX(side) {
    const cx = window.innerWidth / 2;
    const hw = halfWidth();
    return side === "l" ? cx - leftFrac * hw : cx + rightFrac * hw;
  }

  function positionHandles() {
    markerL.style.left = `${markerX("l")}px`;
    markerR.style.left = `${markerX("r")}px`;
    markerL.style.top = "50%";
    markerR.style.top = "50%";
  }

  function spacingHint() {
    const diff = Math.abs(leftFrac - rightFrac);
    if (!equalLock && diff > 0.02) {
      return "L/R spacing unequal — turn Equal lock on, or match by eye";
    }
    return "Drag L/R markers · aim vertical line at fairway target";
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
    const cx = w / 2;
    const cy = h / 2;
    const color = COLORS[colorIndex];
    const lineW = thick ? 4 : 2;
    const dash = thick ? [14, 10] : [10, 8];
    const lx = markerX("l");
    const rx = markerX("r");

    ctx.clearRect(0, 0, w, h);

    const vignette = ctx.createRadialGradient(cx, cy, Math.min(w, h) * 0.2, cx, cy, Math.max(w, h) * 0.75);
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

    // Vertical AIM line
    ctx.beginPath();
    ctx.setLineDash([]);
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, h);
    ctx.stroke();

    // Horizontal MARKER line
    ctx.beginPath();
    ctx.setLineDash(dash);
    ctx.moveTo(0, cy);
    ctx.lineTo(w, cy);
    ctx.stroke();
    ctx.setLineDash([]);

    // Center crosshair
    const box = thick ? 28 : 22;
    ctx.lineWidth = lineW;
    ctx.strokeRect(cx - box / 2, cy - box / 2, box, box);

    // Span between dragged markers
    ctx.globalAlpha = 0.35;
    ctx.lineWidth = Math.max(2, lineW);
    ctx.beginPath();
    ctx.moveTo(lx, cy);
    ctx.lineTo(rx, cy);
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Drop lines at marker positions
    ctx.lineWidth = Math.max(2, lineW - 1);
    for (const x of [lx, rx]) {
      ctx.beginPath();
      ctx.moveTo(x, cy - 34);
      ctx.lineTo(x, cy + 34);
      ctx.stroke();
    }

    // Arrowhead toward fairway
    ctx.beginPath();
    ctx.moveTo(cx, 56);
    ctx.lineTo(cx - 10, 74);
    ctx.lineTo(cx + 10, 74);
    ctx.closePath();
    ctx.fill();

    ctx.restore();
    raf = requestAnimationFrame(drawOverlay);
  }

  function bindDrag(el, side) {
    let dragging = false;
    let pointerId = null;

    const onDown = (e) => {
      if (help && !help.hidden) return;
      dragging = true;
      pointerId = e.pointerId;
      el.classList.add("is-dragging");
      el.setPointerCapture(pointerId);
      e.preventDefault();
    };

    const onMove = (e) => {
      if (!dragging || e.pointerId !== pointerId) return;
      const cx = window.innerWidth / 2;
      const hw = halfWidth();
      let x = e.clientX;

      if (side === "l") {
        x = Math.min(cx - MIN_GAP, Math.max(EDGE_PAD, x));
        leftFrac = clampFrac((cx - x) / hw);
        if (equalLock) rightFrac = leftFrac;
      } else {
        x = Math.max(cx + MIN_GAP, Math.min(window.innerWidth - EDGE_PAD, x));
        rightFrac = clampFrac((x - cx) / hw);
        if (equalLock) leftFrac = rightFrac;
      }

      positionHandles();
      if (!statusEl.classList.contains("error")) {
        setStatus(spacingHint());
      }
      e.preventDefault();
    };

    const onUp = (e) => {
      if (!dragging || e.pointerId !== pointerId) return;
      dragging = false;
      el.classList.remove("is-dragging");
      try {
        el.releasePointerCapture(pointerId);
      } catch (_) {
        /* ignore */
      }
      pointerId = null;
      if (!statusEl.classList.contains("error")) {
        setStatus(spacingHint());
      }
    };

    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
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
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
      }

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
      setStatus(spacingHint());
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
    const c = COLORS[colorIndex];
    btnColor.textContent = `Line: ${c.id}`;
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
    setStatus(spacingHint());
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

  btnStart.addEventListener("click", startCamera);
  btnColor.addEventListener("click", cycleColor);
  btnThick.addEventListener("click", toggleThickness);
  btnLink.addEventListener("click", toggleEqualLock);
  btnHelp.addEventListener("click", openHelp);
  btnCloseHelp.addEventListener("click", closeHelp);

  window.addEventListener("resize", resizeCanvas);
  window.addEventListener("orientationchange", () => {
    setTimeout(resizeCanvas, 250);
  });

  resizeCanvas();
  drawOverlay();
  setStatus("Drag L/R markers anytime · Enable camera for live view");

  try {
    if (!localStorage.getItem("teeAlignHelpSeen")) {
      openHelp();
    }
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
    if (document.visibilityState === "visible" && stream) {
      requestWakeLock();
    }
  });
  btnStart.addEventListener("click", () => {
    requestWakeLock();
  });
})();
