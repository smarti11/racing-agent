// Render a phone-playable flyover video for each Wyndgate hole.
// The picture is the same Esri satellite photo the map uses, tilted and flown
// from the tee to the green. No Google Earth file is required to watch it.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { mkdtemp, readdir, readFile, rm, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire("/tmp/pup/package.json");
const puppeteer = require("puppeteer-core");
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const mapDir = path.join(root, "wyndgate_map");
const stage = path.join(root, "tools", "flyover_stage.html");
const EARTH = 6371000;

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

function framesFor(coords) {
  const total = pathLength(coords) || 1;
  const seconds = Math.max(8, Math.min(12, total / 42));
  const fps = 8;
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

async function holes() {
  const features = JSON.parse(await readFile(path.join(mapDir, "holes.geojson"), "utf8")).features;
  const pins = JSON.parse(await readFile(path.join(mapDir, "pins.geojson"), "utf8")).features;
  const pinByHole = new Map(pins.map((feature) => [feature.properties.hole, pointOf(feature)]));
  return features.map((feature) => {
    const props = feature.properties;
    let coords = feature.geometry.coordinates.map((c) => [c[0], c[1]]);
    const pin = pinByHole.get(props.hole);
    if (pin) {
      const start = haversine(coords[0][0], coords[0][1], pin[0], pin[1]);
      const end = haversine(coords[coords.length - 1][0], coords[coords.length - 1][1], pin[0], pin[1]);
      if (start + 25 < end) coords = coords.slice().reverse();
    }
    return {
      course: "wyndgate",
      hole: props.hole,
      label: "Wyndgate " + props.hole,
      coords,
      frames: framesFor(coords),
    };
  });
}

function encode(frameDir, count, outFile) {
  return new Promise((resolve, reject) => {
    const proc = spawn("ffmpeg", [
      "-y", "-framerate", "8", "-start_number", "0",
      "-i", path.join(frameDir, "frame-%03d.jpg"),
      "-frames:v", String(count),
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30",
      "-movflags", "+faststart",
      outFile,
    ], { stdio: ["ignore", "ignore", "pipe"] });
    let err = "";
    proc.stderr.on("data", (chunk) => { err += chunk; });
    proc.on("close", (code) => (code === 0 ? resolve() : reject(new Error(err.slice(-500)))));
  });
}

async function renderHole(page, hole, frameDir) {
  for (const name of await readdir(frameDir)) {
    if (name.startsWith("frame-")) await unlink(path.join(frameDir, name));
  }
  await page.evaluate((label, coords) => {
    window.setLabel(label);
    window.showHole(coords);
  }, hole.label, hole.coords);
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
      quality: 76,
      path: path.join(frameDir, "frame-" + String(i).padStart(3, "0") + ".jpg"),
    });
  }
}

async function main() {
  const wanted = process.argv.slice(2);
  const all = await holes();
  const list = wanted.length
    ? all.filter((hole) => wanted.includes(String(hole.hole)) || wanted.includes("wyndgate-" + hole.hole))
    : all;
  if (!list.length) throw new Error("No holes matched " + wanted.join(" "));
  const browser = await puppeteer.launch({
    executablePath: "/usr/local/bin/google-chrome",
    headless: "new",
    args: ["--no-sandbox", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist", "--enable-webgl"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 960, height: 540 });
  await page.goto("file://" + stage, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForFunction("window.mapReady === true", { timeout: 30000 });
  const frameDir = await mkdtemp(path.join(tmpdir(), "wyndgate-fly-"));
  try {
    for (const hole of list) {
      const started = Date.now();
      const outFile = path.join(mapDir, "flyover-" + hole.course + "-" + hole.hole + ".mp4");
      await renderHole(page, hole, frameDir);
      await encode(frameDir, hole.frames.length, outFile);
      const { size } = await import("node:fs").then((fs) => fs.promises.stat(outFile));
      console.log(hole.label, hole.frames.length + " frames", Math.round(size / 1024) + "KB", Math.round((Date.now() - started) / 1000) + "s");
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
