# Wyndgate Golf Map

GPS-aware map for **The Wyndgate**, 1975 West Gunn Road, Rochester Hills, MI 48306.

This site is separate from the Oakland University golf map. It has its own folder and must be uploaded to its own Cloudflare project. Uploading these files into the OU project (`tiny-thunder-291b`) replaces the OU map.

## Features

- Satellite map of the 18-hole course, black tees only (par 72, 7,329 yards, 76.2/148)
- Tap a hole to see par and black-tee yardage, then **Fly over** from tee to green
- **Reset** clears the selected hole and zooms back out. Scores stay saved
- Live yards to the green from your GPS, with a short bar on a phone
- Scorecard: say the strokes or type them. Out, In, and the full 18. Scores stay in this browser until you tap Clear

Westwynd, the course on Adams Road, is not included.

## Data sources

- Hole lines, greens, fairways, tees, pins, and cart paths: [OpenStreetMap](https://www.openstreetmap.org/) contributors
- Black-tee par and yardage: published Wyndgate scorecard
- The pin on the map is the parking spot OpenStreetMap has for 1975 West Gunn Road
- Imagery: Esri World Imagery

A few drawn hole lines are a little shorter or longer than the printed black-tee yardage. The number on the card is the printed yardage. The line on the map follows the OpenStreetMap drawing.

## Run locally

```bash
cd wyndgate_map
python3 -m http.server 8093
```

Open `http://localhost:8093`. GPS needs HTTPS or localhost.

## Deploy

Create a **new** Cloudflare Worker. Do not open `tiny-thunder-291b`.

1. In the Cloudflare dashboard, go to **Workers & Pages**.
2. **Create** a Worker and name it something like `wyndgate`.
3. Open that new Worker, then **New deployment**.
4. Select every file inside `wyndgate_map/` (Command-A in that folder) and upload them together. `index.html` must sit next to `app.js` and the `.geojson` files, not inside another folder.

A new deployment replaces every file in that project, so upload the whole folder each time.
