# Tee Align

Simple iPhone camera overlay for greenskeepers: square tee markers to a fairway target.

## How to use on the course

1. Open `index.html` in **Safari on iPhone** (see hosting below — camera requires HTTPS).
2. Tap **Enable camera** and allow access.
3. Stand behind the teeing ground, looking down the hole.
4. Put the vertical **AIM** line on the fairway spot you want the tee to face.
5. **Drag** the on-screen **L** and **R** markers along the horizontal line to your desired width (**Equal lock** keeps them mirrored).
6. Place the physical tee markers to match those handles.

Use **Line color** if lime washes out against grass or sky. **Thick lines** helps in bright sun.

## Run locally (Mac / PC)

```bash
cd tee_align
python3 -m http.server 8090
```

Then open `http://localhost:8090` on that same machine.  
iPhone camera access needs a **secure origin** (HTTPS). Localhost works on the computer; for a phone on the course, host this folder on any HTTPS static host (GitHub Pages, Netlify, Cloudflare Pages, etc.) or use a tunnel such as `ngrok http 8090`.

## Files

| File | Purpose |
|---|---|
| `index.html` | Page shell |
| `styles.css` | Layout / outdoor-readable HUD |
| `app.js` | Rear camera + aim/marker overlay |

No build step and no backend.
