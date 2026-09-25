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
sudo apt install wlr-randr
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

## Display orientation

Use the **Display orientation** buttons to select landscape, portrait (90° or
270°), or upside-down landscape. This rotates the entire Pi display immediately
through labwc, without restarting UxPlay, and also works while the receiver is
stopped. Video flips remain separate controls.

The controller automatically selects the only enabled display. For multiple
displays, add `Environment=DISPLAY_OUTPUT=HDMI-A-1` to the controller service,
using the output name reported by `wlr-randr` in the Pi's Wayland session.
`WLR_RANDR_BIN` overrides the default `/usr/bin/wlr-randr` path. After changing
the service, run `systemctl --user daemon-reload` and
`systemctl --user restart airplay-control.service`.

Rotation lasts for the current labwc session; it is not saved across compositor
restarts or reboots. It changes the display layout, not the orientation selected
by the mirroring device or its app.

The implementation uses the [wlr-randr output transform options](https://github.com/emersion/wlr-randr/blob/master/main.c).

## iPhone Home Screen

The UI is a small installable web app with a manifest, service worker and Apple mobile-web-app metadata. In Safari use **Share → Add to Home Screen**. It launches in standalone mode.

A true Apple **App Clip** is a native iOS feature and requires an iOS/App Store project plus associated-domain setup; this Flask UI is instead a PWA/Home Screen app.

## API

### Restart labwc

Use **Restart labwc** in the UI or `POST /api/labwc/restart` to run
`systemctl --user restart labwc.service`. This restarts the existing user service
installed by this project. It does not launch a separate compositor or restart
UxPlay. AirPlay may disconnect; start the receiver again if needed. A successful
response means the systemd restart completed; the display may still be initializing.
Service errors return 503. Run the controller as the user who owns the labwc service.

### Display orientation

`GET /api/display` returns the selected output, mode, and transform.
To rotate it, send:

```http
PUT /api/display
Content-Type: application/json

{"mode": "portrait-right"}
```

Modes: `landscape`, `portrait-right`, `portrait-left`, `landscape-flipped`.
Repeating the current mode is a no-op. Invalid modes return 400; unavailable
displays or a missing/failed `wlr-randr` return 503.

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
