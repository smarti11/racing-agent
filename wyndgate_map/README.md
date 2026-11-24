# Wyndgate Golf Map

GPS-aware map for **The Wyndgate**, 1975 West Gunn Road, Rochester Hills, MI 48306.

This site is separate from the Oakland University golf map. It has its own folder and must be uploaded to its own Cloudflare project. Uploading these files into the OU project (`tiny-thunder-291b`) replaces the OU map.

## Features

- Satellite map of the 18-hole course (par 72). Pick Black, Blue, Silver, Silver/Green, Green, Black (M), or Gold. Black is 7,329 yards, 76.2/148
- Tap a hole to see par, handicap, and the yardage for the tee you picked, then **Fly over** from tee to green on the map
- **Video** plays a satellite flyover of that hole. A Scottish voice names the hole, the par, and the yardage from the tee you picked
- **Yardage curves** on the selected hole: a thin red line at 100 yards from the middle of the green, white at 150, and blue at 200. The lines are finer than the cart paths. A curve that would fall behind the tee is left off. Reset clears them
- **Breaks** zooms into the green. A color wash and arrows show which way a ball rolls, from the 2016 government lidar scan of Oakland County. Drag the white ball and the red flag. The gold line is a putt that finishes in the hole, and the words say how far left or right to start it. The scan is smoothed over a few meters, so it shows the general fall, not a break of an inch or two
- **Reset** clears the selected hole and zooms back out. Scores stay saved
- Front, center, and back of the green from your GPS, in one short bar on a phone. Tap the map to measure to a bunker or a layup. Center puts the number back on the middle of the green.
- Scorecard: say the strokes or type them. Out, In, and the full 18. Men's or Women's changes the handicap number under each hole. The gold number is the plays-like yardage: one yard added for every three feet the green sits above that tee, and one yard subtracted for every three feet it sits below. Elevations are from USGS 3DEP along the mapped hole. Scores stay in this browser until you tap Clear. **Save this score** opens the phone share sheet so the card can be kept in Files or Notes
- Live **wind** on the map: speed, the direction it is coming from, humidity, and, once a hole is selected, whether that wind is into you or helping. The reading is the latest observation from Pontiac airport, the National Weather Service station nearest the course, and it refreshes while the map is open.

Westwynd, the course on Adams Road, is not included.

## Data sources

- Hole lines, greens, fairways, tees, pins, and cart paths: [OpenStreetMap](https://www.openstreetmap.org/) contributors
- Par, tee yardage, and ratings: the [GolfCore Wyndgate card](https://www.golfcore.org/courses/wyndgate/#course-map). Men's and women's handicaps: the [18Birdies scorecard](https://18birdies.com/golf-courses/club/b3f9ffc0-86ac-11e4-8c28-020000005b00/the-wyndgate-golf-and-country-club) for the same course. Westwynd is a different course and is not this card
- The pin on the map is the parking spot OpenStreetMap has for 1975 West Gunn Road
- Imagery: Esri World Imagery (live map). Hole **Video** flyovers are Mapbox Satellite captures baked into MP4s (no live Mapbox tile use on playback).
- Plays-like elevation: USGS 3DEP at the mapped tee and green
- Green slope: USGS 3DEP 1-meter elevation from the 2016 Oakland County lidar, smoothed over about 3 meters
- Wind: [National Weather Service](https://www.weather.gov/) observation at Pontiac airport (KPTK)

A few drawn hole lines are a little shorter or longer than the printed black-tee yardage. The number on the card is the printed yardage. The line on the map follows the OpenStreetMap drawing.

## Run locally

```bash
cd wyndgate_map
python3 -m http.server 8093
```

Open `http://localhost:8093`. GPS needs HTTPS or localhost.

## Deploy

Preferred (same pattern as Indianwood): `wrangler.toml` names the worker `bold-cake-92fe` (the live Workers URL the phone opens) and serves this folder as assets.

On the Mac Mini (repo at `~/racing-agent`):

```bash
cd ~/racing-agent
git fetch origin
git checkout cursor/wyndgate-yardage-rings-505a
git pull origin cursor/wyndgate-yardage-rings-505a
cd ~/racing-agent/wyndgate_map
npx wrangler deploy
```

Live URL: https://bold-cake-92fe.smarti2006.workers.dev/

Do **not** deploy into the OU worker (`tiny-thunder-291b`). Do **not** deploy only to a separate `wyndgate` worker name — that leaves `bold-cake-92fe` on the old watermarked build. `npx wrangler deploy` from `wyndgate_map/` updates `bold-cake-92fe` because `wrangler.toml` sets `name = "bold-cake-92fe"`.

Dashboard upload still works: open the existing Worker named `bold-cake-92fe`, then **New deployment** and upload every file inside `wyndgate_map/` so `index.html` sits next to `app.js` and the `.geojson` files. Do **not** use an old `wyndgate_map.zip` from a PR comment — those packages can predate the Basemaps `cb1_…` key.

### CARTO label watermark

Label tiles use CARTO Basemaps `light_only_labels` with `?key=cb1_5dhw_1_df8e4cfc1a9a6aed2d27b170` (same key as OU). A Developers JWT in `?key=` still returns watermarked tiles.

After deploy, hard-refresh the phone/browser (iOS Safari: open the URL once in Safari, pull to refresh, or clear Website Data for the workers.dev host). Then confirm:

1. View Source / Network for `app.js` — it must contain `cb1_5dhw_…`, not a long `eyJ…` JWT.
2. Network tile requests to `basemaps.cartocdn.com/.../light_only_labels/...png?key=cb1_…` — response `etag` must **not** start with `wm-`.
