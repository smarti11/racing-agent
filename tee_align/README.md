# Tee Align

iPhone camera overlay for greenskeepers: square tee markers to a fairway target.

## Features

- AIM line + rotatable tee-face line (buttons or two-finger twist)
- Draggable L/R markers with equal-lock
- Phone **level bubble** + **Snap level** (gravity)
- **Freeze** frame while you walk out to place markers
- **Sun mode** for outdoor contrast
- Spacing badge (EQUAL / UNEVEN)
- **Save photo** of the lined-up view

## How to use on the course

1. Open in **Safari on iPhone** (HTTPS required for camera).
2. Tap **Enable camera** and allow access (and motion, if asked).
3. Stand behind the tee, looking down the hole. Keep the level bubble near center.
4. Put **AIM** on the fairway target. Tap **Snap level** or rotate the tee-face line.
5. Drag **L/R** for spacing. Tap **Freeze**, place physical markers, then **Save photo** if you want a record.

## Deploy / update Cloudflare

Upload only these files (do **not** upload `wrangler.toml`):

- `index.html`
- `app.js`
- `styles.css`

## Local preview

```bash
cd tee_align
python3 -m http.server 8090
```

Open `http://localhost:8090` on the same machine.
