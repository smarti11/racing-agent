# Passi di Firenze

Interactive walking audio tour of Florence’s historic center.

## Features

- **GPS unlock** — stops unlock when you are within ~90 m (configurable in `js/tour-data.js`)
- **I’m here** — manual unlock for desktop testing or poor GPS in alleys
- **Map** — Leaflet + CARTO/OSM basemap with numbered pins
- **Scripts + placeholder audio** — full narration text per stop; soft ambient WAVs stand in until real voiceovers exist
- **Progress** — unlocked / heard state saved in `localStorage`

## Route (9 stops, ~4 km)

1. Piazza del Duomo  
2. Baptistery  
3. Piazza della Repubblica  
4. Orsanmichele  
5. Piazza della Signoria  
6. Ponte Vecchio  
7. Oltrarno (Via Guicciardini)  
8. Piazzale Michelangelo  
9. Piazza Santa Croce  

## Run locally

Serve the folder over HTTP (required for geolocation and audio):

```bash
cd florence-tour
python3 -m http.server 8090
```

Open http://localhost:8090/

## Replace placeholder audio

Files in `audio/*.wav` are quiet ambient pads. Drop in recorded MP3/WAV voiceovers with the same filenames (or update paths in `js/tour-data.js`). Keep the on-screen scripts in sync with the recordings.

## Notes

- First stop (Duomo) is unlocked by default.
- Finishing playback (or **Mark heard · next**) unlocks the following stop so the loop stays walkable without forcing every GPS ping.
- Location permission is optional if you always use **I’m here**.
