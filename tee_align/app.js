(() => {
  const video = document.getElementById("camera");
  const canvas = document.getElementById("overlay");
  const ctx = canvas.getContext("2d");
  const statusEl = document.getElementById("status");
  const btnStart = document.getElementById("btn-start");
  const liveControls = document.getElementById("live-controls");
  const btnColor = document.getElementById("btn-color");
  const btnThick = document.getElementById("btn-thick");
  const help = document.getElementById("help");
  const btnHelp = document.getElementById("btn-help");
  const btnCloseHelp = document.getElementById("btn-close-help");

  const COLORS = [
    { id: "lime", value: "#c8f542", glow: "rgba(200, 245, 66, 0.35)" },
    { id: "white", value: "#ffffff", glow: "rgba(255, 255, 255, 0.3)" },
    { id: "yellow", value: "#ffe566", glow: "rgba(255, 229, 102, 0.35)" },
    { id: "black", value: "#111111", glow: "rgba(0, 0, 0, 0.35)" },
  ];

  let colorIndex = 0;
  let thick = true;
  let stream = null;
  let raf = 0;

  function setStatus(msg, isError = false) {
    statusEl.textContent = msg || "";
    statusEl.classList.toggle("error", Boolean(isError));
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
  }

  function drawOverlay() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    const cx = w / 2;
    const cy = h / 2;
    const color = COLORS[colorIndex];
    const lineW = thick ? 4 : 2;
    const dash = thick ? [14, 10] : [10, 8];

    ctx.clearRect(0, 0, w, h);

    // Soft vignette so lines read outdoors
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

    // Vertical AIM line (line of play)
    ctx.beginPath();
    ctx.setLineDash([]);
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, h);
    ctx.stroke();

    // Horizontal MARKER line (tee face)
    ctx.beginPath();
    ctx.setLineDash(dash);
    ctx.moveTo(0, cy);
    ctx.lineTo(w, cy);
    ctx.stroke();
    ctx.setLineDash([]);

    // Center crosshair box
    const box = thick ? 28 : 22;
    ctx.lineWidth = lineW;
    ctx.strokeRect(cx - box / 2, cy - box / 2, box, box);

    // Tick marks for equal left/right spacing cues
    const ticks = [0.18, 0.32];
    ctx.lineWidth = Math.max(2, lineW - 1);
    for (const t of ticks) {
      const dx = w * t;
      for (const side of [-1, 1]) {
        const x = cx + side * dx;
        ctx.beginPath();
        ctx.moveTo(x, cy - 12);
        ctx.lineTo(x, cy + 12);
        ctx.stroke();
      }
    }

    // Arrowhead toward fairway (top of AIM line)
    ctx.beginPath();
    ctx.moveTo(cx, 56);
    ctx.lineTo(cx - 10, 74);
    ctx.lineTo(cx + 10, 74);
    ctx.closePath();
    ctx.fill();

    ctx.restore();
    raf = requestAnimationFrame(drawOverlay);
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
      setStatus("Aim vertical line at fairway target · place markers on horizontal line");
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
    document.documentElement.style.setProperty("--line", c.value);
  }

  function toggleThickness() {
    thick = !thick;
    btnThick.textContent = thick ? "Thick lines" : "Thin lines";
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

  btnStart.addEventListener("click", startCamera);
  btnColor.addEventListener("click", cycleColor);
  btnThick.addEventListener("click", toggleThickness);
  btnHelp.addEventListener("click", openHelp);
  btnCloseHelp.addEventListener("click", closeHelp);

  window.addEventListener("resize", resizeCanvas);
  window.addEventListener("orientationchange", () => {
    setTimeout(resizeCanvas, 250);
  });

  resizeCanvas();
  drawOverlay();

  try {
    if (!localStorage.getItem("teeAlignHelpSeen")) {
      openHelp();
    }
  } catch (_) {
    openHelp();
  }

  // Wake Lock when supported — keeps screen on while setting markers
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
