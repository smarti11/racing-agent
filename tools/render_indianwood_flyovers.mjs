// Render phone-playable flyover videos for Indianwood Old + New holes.
// Same Esri + MapLibre tilt path used for OU / Wyndgate.
//
// Quality defaults (2026-11): 1280×720 @ 15fps, JPEG ~90, libx264 CRF ~26.
// Prior defaults (kept as CLI overrides): 960×540 @ 8fps, JPEG 76, CRF 30.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readdir, readFile, rm, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire("/tmp/pup/package.json");
const puppeteer = require("puppeteer-core");
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const mapDir = path.join(root, "apps", "indianwood-course");
const stage = path.join(root, "tools", "flyover_stage.html");
const EARTH = 6371000;
const COURSE_LABEL = { old: "Old", new: "New" };

const DEFAULTS = {
  width: 1280,
  height: 720,
  fps: 15,
  crf: 26,
  jpeg: 90,
  scale: 2,
  outdir: mapDir,
  imagery: "esri",
  suffix: "",
};

function parseArgs(argv) {
  const opts = { ...DEFAULTS, holes: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--width") opts.width = Number(argv[++i]);
    else if (a === "--height") opts.height = Number(argv[++i]);
    else if (a === "--fps") opts.fps = Number(argv[++i]);
    else if (a === "--crf") opts.crf = Number(argv[++i]);
    else if (a === "--jpeg") opts.jpeg = Number(argv[++i]);
    else if (a === "--scale") opts.scale = Number(argv[++i]);
    else if (a === "--outdir") opts.outdir = path.resolve(argv[++i]);
    else if (a === "--imagery") opts.imagery = String(argv[++i] || "esri").toLowerCase();
    else if (a === "--suffix") opts.suffix = String(argv[++i] || "");
    else if (a === "--legacy") {
      opts.width = 960;
      opts.height = 540;
      opts.fps = 8;
      opts.crf = 30;
      opts.jpeg = 76;
      opts.scale = 1;
    } else if (a.startsWith("-")) {
      throw new Error("Unknown flag " + a);
    } else {
      opts.holes.push(a);
    }
  }
  if (opts.imagery !== "esri" && opts.imagery !== "mapbox") {
    throw new Error("--imagery must be esri or mapbox");
  }
  if (opts.imagery === "mapbox" && !opts.suffix) opts.suffix = "-mapbox";
  return opts;
}

function haversine(lon1, lat1, lon2, lat2) {
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dlat = ((lat2 - lat1) * Math.PI) / 180;
  const dlon = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dlat / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dlon / 2) ** 2;
  return 2 * EARTH * Math.asin(Math.sqrt(a));
}

function bearing(lon1, lat1, lon2, lat2) {
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dlon = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(dlon) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dlon);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function pathLength(coords) {
  let total = 0;
  for (let i = 1; i < coords.length; i++) {
    total += haversine(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1]);
  }
  return total;
}

function headingAt(coords, index) {
  const next = Math.min(coords.length - 1, index + 1);
  if (next === index && index > 0) {
    return bearing(coords[index - 1][0], coords[index - 1][1], coords[index][0], coords[index][1]);
  }
  return bearing(coords[index][0], coords[index][1], coords[next][0], coords[next][1]);
}

function pointAlong(coords, distance) {
  if (coords.length === 1 || distance <= 0) {
    return { lon: coords[0][0], lat: coords[0][1], heading: headingAt(coords, 0) };
  }
  let remaining = distance;
  for (let i = 0; i < coords.length - 1; i++) {
    const start = coords[i];
    const end = coords[i + 1];
    const segment = haversine(start[0], start[1], end[0], end[1]);
    const heading = bearing(start[0], start[1], end[0], end[1]);
    if (remaining <= segment || i === coords.length - 2) {
      const fraction = segment === 0 ? 0 : Math.min(1, remaining / segment);
      return {
        lon: start[0] + (end[0] - start[0]) * fraction,
        lat: start[1] + (end[1] - start[1]) * fraction,
        heading,
      };
    }
    remaining -= segment;
  }
  const last = coords[coords.length - 1];
  return { lon: last[0], lat: last[1], heading: headingAt(coords, coords.length - 1) };
}

function framesFor(coords, fps) {
  const total = pathLength(coords) || 1;
  const seconds = Math.max(8, Math.min(12, total / 42));
  const count = Math.round(seconds * fps);
  const frames = [];
  for (let i = 0; i < count; i++) {
    const u = count === 1 ? 1 : i / (count - 1);
    const travel = Math.min(1, u / 0.8);
    const eased = travel < 0.5 ? 2 * travel * travel : 1 - (-2 * travel + 2) ** 2 / 2;
    const settle = Math.min(1, Math.max(0, (u - 0.62) / 0.18));
    const smooth = settle * settle * (3 - 2 * settle);
    const dist = eased * total;
    const lookAhead = 34 * (1 - smooth);
    const look = pointAlong(coords, Math.min(total, dist + lookAhead));
    frames.push({
      lon: look.lon,
      lat: look.lat,
      heading: look.heading,
      pitch: 68 - 36 * smooth,
      zoom: 18.65 + 0.3 * smooth,
    });
  }
  return frames;
}

function pointOf(feature) {
  const geometry = feature.geometry;
  if (geometry.type === "Point") return geometry.coordinates;
  const ring = geometry.coordinates[0];
  let lon = 0;
  let lat = 0;
  for (const point of ring) {
    lon += point[0];
    lat += point[1];
  }
  return [lon / ring.length, lat / ring.length];
}

async function holes(fps) {
  const features = JSON.parse(await readFile(path.join(mapDir, "holes.geojson"), "utf8")).features;
  const pins = JSON.parse(await readFile(path.join(mapDir, "pins.geojson"), "utf8")).features;
  const pinByKey = new Map(
    pins.map((feature) => [
      feature.properties.course + ":" + feature.properties.hole,
      pointOf(feature),
    ])
  );
  return features
    .map((feature) => {
      const props = feature.properties;
      let coords = feature.geometry.coordinates.map((c) => [c[0], c[1]]);
      const pin = pinByKey.get(props.course + ":" + props.hole);
      if (pin) {
        const start = haversine(coords[0][0], coords[0][1], pin[0], pin[1]);
        const end = haversine(
          coords[coords.length - 1][0],
          coords[coords.length - 1][1],
          pin[0],
          pin[1]
        );
        if (start + 25 < end) coords = coords.slice().reverse();
      }
      const course = props.course === "new" ? "new" : "old";
      return {
        course,
        hole: props.hole,
        label: (COURSE_LABEL[course] || course) + " " + props.hole,
        coords,
        frames: framesFor(coords, fps),
      };
    })
    .sort((a, b) => a.course.localeCompare(b.course) || a.hole - b.hole);
}

function encode(frameDir, count, outFile, opts) {
  return new Promise((resolve, reject) => {
    const proc = spawn(
      "ffmpeg",
      [
        "-y",
        "-framerate",
        String(opts.fps),
        "-start_number",
        "0",
        "-i",
        path.join(frameDir, "frame-%03d.jpg"),
        "-frames:v",
        String(count),
        "-vf",
        `scale=${opts.width}:${opts.height}`,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        String(opts.crf),
        "-movflags",
        "+faststart",
        outFile,
      ],
      { stdio: ["ignore", "ignore", "pipe"] }
    );
    let err = "";
    proc.stderr.on("data", (chunk) => {
      err += chunk;
    });
    proc.on("close", (code) => (code === 0 ? resolve() : reject(new Error(err.slice(-500)))));
  });
}

async function renderHole(page, hole, frameDir, jpegQuality) {
  for (const name of await readdir(frameDir)) {
    if (name.startsWith("frame-")) await unlink(path.join(frameDir, name));
  }
  await page.evaluate(
    (label, coords) => {
      window.setLabel(label);
      window.showHole(coords);
    },
    hole.label,
    hole.coords
  );
  const warm = [0, Math.floor(hole.frames.length / 2), hole.frames.length - 1];
  for (const index of warm) {
    const frame = hole.frames[index];
    await page.evaluate((f) => window.setCam(f.lon, f.lat, f.zoom, f.heading, f.pitch), frame);
    await page.evaluate(() => window.settle());
  }
  for (let i = 0; i < hole.frames.length; i++) {
    const frame = hole.frames[i];
    await page.evaluate((f) => window.setCam(f.lon, f.lat, f.zoom, f.heading, f.pitch), frame);
    await page.evaluate(() => window.settle());
    await page.screenshot({
      type: "jpeg",
      quality: jpegQuality,
      path: path.join(frameDir, "frame-" + String(i).padStart(3, "0") + ".jpg"),
    });
  }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const wanted = opts.holes;
  const all = await holes(opts.fps);
  const list = wanted.length
    ? all.filter(
        (hole) =>
          wanted.includes(String(hole.hole)) ||
          wanted.includes(hole.course + "-" + hole.hole) ||
          wanted.includes(hole.course)
      )
    : all;
  if (!list.length) throw new Error("No holes matched " + wanted.join(" "));
  await mkdir(opts.outdir, { recursive: true });
  console.log(
    `Quality: ${opts.width}x${opts.height} @ ${opts.fps}fps, CRF ${opts.crf}, JPEG ${opts.jpeg}, scale ${opts.scale}, imagery ${opts.imagery} — ${list.length} hole(s) → ${opts.outdir}`
  );
  const browser = await puppeteer.launch({
    executablePath: "/usr/local/bin/google-chrome",
    headless: "new",
    args: [
      "--no-sandbox",
      "--enable-unsafe-swiftshader",
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--ignore-gpu-blocklist",
      "--enable-webgl",
    ],
  });
  const page = await browser.newPage();
  await page.setViewport({
    width: opts.width,
    height: opts.height,
    deviceScaleFactor: opts.scale,
  });
  const stageUrl = "file://" + stage + "?imagery=" + encodeURIComponent(opts.imagery);
  await page.goto(stageUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForFunction("window.mapReady === true", { timeout: 60000 });
  const frameDir = await mkdtemp(path.join(tmpdir(), "indianwood-fly-"));
  try {
    for (const hole of list) {
      const started = Date.now();
      const outFile = path.join(
        opts.outdir,
        "flyover-" + hole.course + "-" + hole.hole + opts.suffix + ".mp4"
      );
      await renderHole(page, hole, frameDir, opts.jpeg);
      await encode(frameDir, hole.frames.length, outFile, opts);
      const { size } = await import("node:fs").then((fs) => fs.promises.stat(outFile));
      console.log(
        hole.label,
        hole.frames.length + " frames",
        Math.round(size / 1024) + "KB",
        Math.round((Date.now() - started) / 1000) + "s"
      );
    }
  } finally {
    await rm(frameDir, { recursive: true, force: true });
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
