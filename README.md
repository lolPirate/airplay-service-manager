# AirPlay Pi Controller

A lightweight Flask controller for a Raspberry Pi running **labwc + UxPlay**.

## Design

- `labwc` is the only display component that runs continuously under `systemd --user`.
- The Flask app owns the UxPlay process directly; there is no always-on `uxplay.service`.
- `PUT /api/session` is idempotent:
  - same requested profile/flip state while already running => no-op;
  - different requested profile/flip state => stop current UxPlay and replace it;
  - stopped => start it.
- `DELETE /api/session` is idempotent: stopping an already-stopped receiver succeeds.
- Horizontal and vertical flips use UxPlay `-f H` / `-f V`; both together use `-f I`.
- Audio/video mode uses V4L2 H.264 decoding + `waylandsink`.
- Audio + artwork mode uses `-vs 0 -ca -async`.

## Project layout

```
airplay-control/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── controller.py
│   ├── routes.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/app.css
│       ├── js/app.js
│       ├── manifest.webmanifest
│       ├── sw.js
│       └── icons/
├── systemd/
│   ├── airplay-control.service
│   └── labwc.service
├── requirements.txt
└── run.py
```

## Install

Copy the project to `/home/deb/airplay-control`, then:

```bash
cd /home/deb/airplay-control
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Disable the old always-on UxPlay service if it exists:

```bash
systemctl --user disable --now uxplay.service
```

Install/refresh the user services:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/labwc.service ~/.config/systemd/user/labwc.service
cp systemd/airplay-control.service ~/.config/systemd/user/airplay-control.service
systemctl --user daemon-reload
systemctl --user enable --now labwc.service airplay-control.service
```

For boot without an interactive login:

```bash
sudo loginctl enable-linger deb
```

Open from another device on the LAN:

```
http://raspi:5000
```

## Existing Pi configuration

The app assumes:

- labwc creates `/run/user/1000/wayland-0`.
- HDMI/OpenAL audio is already configured in `~/.config/alsoft.conf` (for example `plughw:1,0`).
- UxPlay is `/usr/bin/uxplay`.

If your UxPlay binary is elsewhere, set `UXPLAY_BIN` in the controller service environment or change `app/config.py`.

## iPhone Home Screen

The UI is a small installable web app with a manifest, service worker and Apple mobile-web-app metadata. In Safari use **Share → Add to Home Screen**. It launches in standalone mode.

A true Apple **App Clip** is a native iOS feature and requires an iOS/App Store project plus associated-domain setup; this Flask UI is instead a PWA/Home Screen app.

## API

### Status

```http
GET /api/session
```

### Start or apply configuration

```http
PUT /api/session
Content-Type: application/json

{
  "profile": "av",
  "flip_horizontal": false,
  "flip_vertical": false
}
```

Profiles:

- `av`
- `audio`

### Stop

```http
DELETE /api/session
```

## Notes

The controller keeps a runtime state file in `/run/user/1000` and verifies `/proc/<pid>/cmdline` before terminating a stored PID. This avoids killing an unrelated process if a stale PID is ever reused.
