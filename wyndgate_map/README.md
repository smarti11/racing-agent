# Wyndgate Golf Map

GPS-aware map for **The Wyndgate**, 1975 West Gunn Road, Rochester Hills, MI 48306.

This site is separate from the Oakland University golf map. It has its own folder and must be uploaded to its own Cloudflare project. Uploading these files into the OU project (`tiny-thunder-291b`) replaces the OU map.

## Features

- Satellite map of the 18-hole course (par 72). Pick Black, Blue, Silver, Silver/Green, Green, Black (M), or Gold. Black is 7,329 yards, 76.2/148
- Tap a hole to see par, handicap, and the yardage for the tee you picked, then **Fly over** from tee to green on the map
- **Video** plays a satellite flyover of that hole. A Scottish voice names the hole, the par, and the yardage from the tee you picked
- **Reset** clears the selected hole and zooms back out. Scores stay saved
- Front, center, and back of the green from your GPS, in one short bar on a phone. Tap the map to measure to a bunker or a layup. Center puts the number back on the middle of the green.
- Scorecard: say the strokes or type them. Out, In, and the full 18. Men's or Women's changes the handicap number under each hole. Scores stay in this browser until you tap Clear

Westwynd, the course on Adams Road, is not included.

## Data sources

- Hole lines, greens, fairways, tees, pins, and cart paths: [OpenStreetMap](https://www.openstreetmap.org/) contributors
- Par, tee yardage, and ratings: the [GolfCore Wyndgate card](https://www.golfcore.org/courses/wyndgate/#course-map). Men's and women's handicaps: the [18Birdies scorecard](https://18birdies.com/golf-courses/club/b3f9ffc0-86ac-11e4-8c28-020000005b00/the-wyndgate-golf-and-country-club) for the same course. Westwynd is a different course and is not this card
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
