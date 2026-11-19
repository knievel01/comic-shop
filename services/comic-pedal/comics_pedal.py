#!/usr/bin/env python3
"""Footswitch capture for the scan station (ADR-0007).

Switch 1 = new comic: creates {SCAN_DIR}/erfassung/<uuid>/.   Switch 2 = photo into the open folder.
A folder is closed by the next press of switch 1 or after IDLE_CLOSE_S without a photo: the first and the last
photo become neu/<uuid>.pdf (two pages), which comics-scan-sync uploads under the same uuid. The folder keeps its
name until comics-folder-rename knows the comic and renames it to the shop handle. Needs python3-evdev, fswebcam
or gphoto2, and img2pdf. Runs as the scan user (systemd unit comics-pedal).

  comics_pedal.py                run the service
  comics_pedal.py --einrichten   forget which switch is which, ask for both again
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("comics_pedal")

SCAN_DIR = Path(os.environ.get("COMICS_SCAN_DIR", "/srv/scans"))
STATE_FILE = Path(os.environ.get("COMICS_PEDAL_STATE", "/var/lib/comics-pedal/pedals.json"))
IDLE_CLOSE_S = float(os.environ.get("COMICS_PEDAL_IDLE_CLOSE_S", "300"))
DEBOUNCE_S = 0.25        # one press may arrive on the keyboard and the mouse node; a quick second tap still counts
EV_KEY = 1               # evdev.ecodes.EV_KEY
STATUS_PORT = int(os.environ.get("COMICS_PEDAL_PORT", "8099"))
CANON_FORMAT = "Medium Fine JPEG"   # 3088x2056, about the size the shop and the recognition need: no conversion
CANON_ROTATE = os.environ.get("COMICS_CANON_ROTATE", "90")   # clockwise; the Canon lies landscape over the comic
MAX_HEFTE = 200                     # comics kept in the station view since the service started
WEBCAM = os.environ.get("COMICS_WEBCAM", "/dev/video0")
VENDOR, PRODUCT = 0x3553, 0xB001          # PCsensor FootSwitch
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
SOUNDS = {  # freedesktop sound theme, installed with the desktop
    "neu": "message", "foto": "camera-shutter", "zu": "complete", "fehler": "dialog-warning",
    "einrichtung": "bell",
}


class CameraHint(Exception):
    """The camera works but is set up wrong; the message tells the person at the station what to change."""


# --- capture ------------------------------------------------------------------------------------------------
def shoot(path: str, run=subprocess.run) -> str | None:
    """One photo to `path`: the Canon if gphoto2 sees one, otherwise the webcam.

    Returns "Canon" or "Webcam" for the camera that took it, None if it failed. A Canon that fails is a failure,
    never a silent webcam photo. Raises CameraHint for a fixable setting."""
    try:
        det = run(["gphoto2", "--auto-detect"], capture_output=True, text=True, timeout=15)
        canon = any(line.strip() for line in det.stdout.splitlines()[2:])
    except (OSError, subprocess.TimeoutExpired):
        canon = False
    try:
        if not canon:
            run(["fswebcam", "-d", WEBCAM, "-r", "1280x720", "--no-banner", "--skip", "8", "--jpeg", "92", path],
                capture_output=True, text=True, timeout=30, check=True)
        else:
            tmp = tempfile.mkdtemp(prefix="comics-pedal-")
            try:
                # save to the SD card: the 450D's internal RAM target fails now and then
                # gphoto2 downloads into a temp file in the working directory: the service's cwd (/) is read-only
                # the right size straight from the camera: no conversion on the laptop, half the USB transfer
                run(["gphoto2", "--quiet", "--set-config", "capturetarget=1", "--set-config",
                     f"imageformat={CANON_FORMAT}"], capture_output=True, text=True, timeout=30, cwd=tmp)
                run(["gphoto2", "--quiet", "--capture-image-and-download", "--filename", f"{tmp}/raw.%C",
                     "--force-overwrite"], capture_output=True, text=True, timeout=60, check=True, cwd=tmp)
                found = sorted(glob.glob(f"{tmp}/raw.*"))
                if not found:                                    # gphoto2 exits 0 even when the download fails
                    raise CameraHint("Kamera hat ausgelöst, aber das Bild kam nicht an (USB-Kabel prüfen)")
                raw = found[0]
                if not raw.lower().endswith((".jpg", ".jpeg")):
                    raise CameraHint("Kamera auf JPEG stellen (Menü: Qualität → JPEG, kein RAW)")
                if CANON_ROTATE in ("90", "180", "270"):
                    # lossless (no re-encoding) and fast; -trim drops the few edge pixels that are not a full block
                    run(["jpegtran", "-rotate", CANON_ROTATE, "-trim", "-copy", "all", "-outfile", path, raw],
                        capture_output=True, timeout=30, check=True)
                else:
                    shutil.move(raw, path)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        return ("Canon" if canon else "Webcam") if os.path.getsize(path) > 0 else None
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("photo failed: %s", e)
        return None


def build_pdf(first: str, last: str, out: str, run=subprocess.run) -> None:
    """Two-page PDF: cover = first photo, back = last photo."""
    run(["img2pdf", first, last, "-o", out], check=True, capture_output=True, timeout=120)


# --- session (pure logic, no hardware) ----------------------------------------------------------------------
class Session:
    """Readers (status, photo) never take `lock`: a photo holds it for seconds. Writers replace lists instead of
    changing them in place, so a reader always sees a consistent snapshot."""

    def __init__(self, base: Path, shoot=shoot, make_pdf=build_pdf, notify=lambda event: None, clock=time.monotonic,
                 idle_close_s: float = IDLE_CLOSE_S, wall=time.time):
        self.base, self.shoot, self.make_pdf, self.notify, self.clock = Path(base), shoot, make_pdf, notify, clock
        self.wall = wall
        self.idle = idle_close_s
        self.folder: Path | None = None
        self.photos: list[Path] = []
        self.touched = 0.0
        self.hefte: list[dict] = []                             # closed comics since start, newest first
        self.files: dict[str, list[str]] = {}                   # comic -> photo file names, for the station view
        self.hint: str | None = None
        self.camera: str | None = None                          # camera of the last good photo
        self.busy = False                                       # a photo is being taken right now
        self.switches = "fehlen"                                # fehlen | einrichtung | bereit (set by run())
        self.lock = threading.RLock()

    def _dir(self, name: str) -> Path:
        d = self.base / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def press_new(self) -> None:
        with self.lock:
            if self.folder is not None and not self.photos:     # nobody shot anything yet: keep this one
                self.touched = self.clock()
                self.notify("neu")
                return
            self.close()
            folder = self._dir("erfassung") / str(uuid.uuid4())
            folder.mkdir()
            self.photos, self.touched, self.folder = [], self.clock(), folder
            self.notify("neu")

    def press_photo(self) -> None:
        with self.lock:
            if self.folder is None:
                self.notify("fehler")                           # first switch 1, else two comics get mixed up
                return
            target = self.folder / f"foto-{len(self.photos) + 1:03d}.jpg"
            self.busy = True
            try:
                ok = self.shoot(str(target))
                self.hint = None
            except CameraHint as e:
                ok, self.hint = False, str(e)
                log.warning("camera: %s", e)
            finally:
                self.busy = False
            if ok:
                if isinstance(ok, str):
                    self.camera = ok
                self.photos = self.photos + [target]
                self.files[self.folder.name] = [p.name for p in self.photos]
                self.touched = self.clock()
                self.notify("foto")
            else:
                target.unlink(missing_ok=True)
                self.notify("fehler")

    def tick(self) -> None:
        with self.lock:
            if self.folder is not None and self.clock() - self.touched >= self.idle:
                self.close()

    def close(self) -> None:
        """Finish the open folder: PDF into neu/, or fehler/ if fewer than two photos."""
        if self.folder is None:
            return
        folder, photos = self.folder, self.photos
        self.folder, self.photos = None, []
        if not photos:
            shutil.rmtree(folder, ignore_errors=True)
            return
        if len(photos) < 2:
            shutil.move(str(folder), str(self._dir("fehler") / folder.name))
            self._remember(folder.name, len(photos), "zu_wenig")
            self.notify("fehler")
            return
        out = self._dir("neu") / f"{folder.name}.pdf"
        part = out.with_name(out.name + ".part")                # the sync only globs *.pdf
        try:
            self.make_pdf(str(photos[0]), str(photos[-1]), str(part))
            os.replace(part, out)
        except (OSError, subprocess.SubprocessError) as e:
            log.error("pdf for %s failed: %s", folder.name, e)
            part.unlink(missing_ok=True)
            shutil.move(str(folder), str(self._dir("fehler") / folder.name))
            self._remember(folder.name, len(photos), "pdf_fehler")
            self.notify("fehler")
            return
        self._remember(folder.name, len(photos), None)
        self.notify("zu")

    def _remember(self, name: str, photos: int, fehler: str | None) -> None:
        self.hefte = ([{"name": name, "fotos": photos, "zu": int(self.wall()), "fehler": fehler}]
                      + self.hefte)[:MAX_HEFTE]
        self.files = {h["name"]: self.files.get(h["name"], []) for h in self.hefte}

    def status(self) -> dict:
        folder, photos = self.folder, self.photos                # one snapshot, see the class docstring
        if folder is None:
            nxt = "Schalter 1: neues Heft"
        elif not photos:
            nxt = "Schalter 2: Cover fotografieren"
        else:
            nxt = "Schalter 2: Rückseite (oder weiteres Foto), Schalter 1: nächstes Heft"
        return {"heft": folder.name if folder else None, "fotos": len(photos), "naechstes": nxt,
                "hefte": list(self.hefte), "hinweis": self.hint, "kamera": self.camera, "aufnahme": self.busy,
                "schalter": self.switches}

    def photo(self, n: int, name: str | None = None) -> Path | None:
        """n-th photo (1-based, -1 = last) of comic `name` (default: the open one), also after it was moved."""
        folder = self.folder
        name = name or (folder.name if folder else None)
        files = [p.name for p in self.photos] if folder is not None and name == folder.name else self.files.get(name)
        if not files:
            return None
        try:
            fname = files[n - 1] if n > 0 else files[n]
        except IndexError:
            return None
        for d in (self.base / "erfassung" / name, self.base / "fehler" / name, self.base / ".umbenannt" / name):
            if (d / fname).is_file():                           # .umbenannt/<id> links to hochgeladen/<handle>
                return d / fname
        return None


# --- switches -----------------------------------------------------------------------------------------------
class Debounce:
    """Per switch; `now` is the event's own timestamp, so presses queued during a photo keep their real spacing."""

    def __init__(self, seconds: float = DEBOUNCE_S, clock=time.monotonic):
        self.seconds, self.clock, self.last = seconds, clock, {}

    def ok(self, key: str, now: float | None = None) -> bool:
        now = self.clock() if now is None else now
        if key in self.last and now - self.last[key] < self.seconds:
            return False
        self.last[key] = now
        return True


def extract_presses(batch) -> list[tuple[str, float]]:
    """[(group key, [events])] -> every key press (value 1, no release/auto-repeat) as (key, time), oldest first."""
    presses = [(key, ev.timestamp()) for key, events in batch for ev in events if ev.type == EV_KEY and ev.value == 1]
    return sorted(presses, key=lambda p: p[1])


def group_key(phys: str) -> str:
    """Both switches have the same USB id, the USB port tells them apart: 'usb-0000:00:14.0-2/input0' -> port."""
    return phys.split("/", 1)[0]


class Calibrator:
    """First press = switch 1, first press of a different pedal = switch 2."""

    def __init__(self):
        self.keys: list[str] = []

    def next_prompt(self) -> str:
        return "schalter1" if not self.keys else "schalter2"

    def feed(self, key: str) -> bool:
        if key not in self.keys:
            self.keys.append(key)
        return len(self.keys) == 2

    def result(self) -> dict:
        return {"schalter1": self.keys[0], "schalter2": self.keys[1]}


def local_origin(origin: str | None) -> bool:
    """Origin of a page on this machine or in the private LAN (the review UI), not some website on the internet."""
    import ipaddress
    from urllib.parse import urlparse
    if not origin:
        return False
    host = urlparse(origin).hostname or ""
    if host in ("localhost", os.uname().nodename) or host.endswith(".local"):
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


# --- status server (127.0.0.1 only, read by the upload page on this machine) --------------------------------
def start_status_server(session: Session, port: int = STATUS_PORT) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _headers(self, code: int, length: int = 0, cache: bool = False) -> None:
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "X-Comics-Pedal")
            self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")   # photos never change
            self.send_header("Content-Length", str(length))

        def do_OPTIONS(self):  # noqa: N802 - http.server API
            self._headers(204)
            self.end_headers()

        def _send(self, code: int, body: bytes = b"", ctype: str = "application/json; charset=utf-8",
                  cache: bool = False) -> None:
            self._headers(code, len(body), cache)
            if body:
                self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            path = self.path.split("?")[0]
            if path == "/status.json":
                return self._send(200, json.dumps(session.status(), ensure_ascii=False).encode())
            m = re.fullmatch(r"(?:/heft/([0-9a-f-]{36}))?/foto/(-?\d+)\.jpg", path)
            p = session.photo(int(m.group(2)), m.group(1)) if m else None
            if p is None:
                return self._send(404)
            self._send(200, p.read_bytes(), "image/jpeg", cache=int(m.group(2)) > 0)

        def do_POST(self):  # noqa: N802
            # on-screen switches; the custom header forces a CORS preflight, so only pages on this LAN may press
            if self.headers.get("X-Comics-Pedal") != "1" or not local_origin(self.headers.get("Origin")):
                return self._send(403)
            action = {"/neu": session.press_new, "/foto": session.press_photo}.get(self.path.split("?")[0])
            if action is None:
                return self._send(404)
            action()
            self._send(200, json.dumps(session.status(), ensure_ascii=False).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# --- hardware loop (not unit-tested, needs the pedals) ------------------------------------------------------
def play(event: str) -> None:
    sound = SOUNDS.get(event)
    path = f"/usr/share/sounds/freedesktop/stereo/{sound}.oga" if sound else ""
    if not path or not os.path.exists(path):
        return
    env = dict(os.environ, XDG_RUNTIME_DIR=f"/run/user/{os.getuid()}")
    try:
        subprocess.Popen(["paplay", path], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def find_switches():
    """{group_key: [InputDevice, ...]} for all PCsensor FootSwitch interfaces."""
    from evdev import InputDevice, list_devices
    groups: dict[str, list] = {}
    for p in list_devices():
        try:
            d = InputDevice(p)
        except OSError:
            continue
        if (d.info.vendor, d.info.product) == (VENDOR, PRODUCT):
            groups.setdefault(group_key(d.phys), []).append(d)
        else:
            d.close()
    return groups


def pressed(devs: dict, timeout: float = 1.0) -> list[tuple[str, float]]:
    """Waits up to `timeout` for input, returns all key presses since the last call (see extract_presses)."""
    fds = {d.fd: (k, d) for k, ds in devs.items() for d in ds}
    ready, _, _ = select.select(list(fds), [], [], timeout)
    batch = []
    for fd in ready:
        key, dev = fds[fd]
        try:
            batch.append((key, list(dev.read())))
        except BlockingIOError:
            pass
    return extract_presses(batch)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if "--einrichten" in sys.argv:
        STATE_FILE.unlink(missing_ok=True)
    session = Session(SCAN_DIR, notify=play)
    start_status_server(session)
    debounce = Debounce()
    while True:
        groups = find_switches()
        if len(groups) < 2:
            session.switches = "fehlen"
            session.tick()
            log.info("waiting for two footswitches (found %d)", len(groups))
            for ds in groups.values():
                for d in ds:
                    d.close()
            time.sleep(5)
            continue
        for ds in groups.values():
            for d in ds:
                try:
                    d.grab()                                    # nothing may be typed into the desktop
                except OSError as e:
                    log.warning("grab failed: %s", e)
        try:
            cfg = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else None
            if cfg and not {cfg["schalter1"], cfg["schalter2"]} <= set(groups):
                log.warning("saved switches not found at their USB ports, setting up again")
                cfg = None
            if cfg is None:
                session.switches = "einrichtung"
                cal = Calibrator()
                log.info("Einrichtung: bitte Fußschalter 1 treten, dann Fußschalter 2")
                play("einrichtung")
                done = False
                while not done:
                    for k, _ in pressed(groups):
                        before = len(cal.keys)
                        done = cal.feed(k)
                        if len(cal.keys) > before:
                            play("neu")
                        if done:
                            break
                cfg = cal.result()
                STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
                STATE_FILE.write_text(json.dumps(cfg))
                log.info("Einrichtung gespeichert: %s", cfg)
            session.switches = "bereit"
            log.info("running: switch 1 = %s, switch 2 = %s", cfg["schalter1"], cfg["schalter2"])
            while True:
                for k, t in pressed(groups):                    # every tap counts, also those queued during a photo
                    if not debounce.ok(k, t):
                        continue
                    if k == cfg["schalter1"]:
                        session.press_new()
                    elif k == cfg["schalter2"]:
                        session.press_photo()
                session.tick()
        except OSError as e:                                    # unplugged: look again
            log.warning("switch lost: %s", e)
            session.switches = "fehlen"
            session.tick()
        finally:
            for ds in groups.values():
                for d in ds:
                    try:
                        d.close()
                    except OSError:
                        pass
            time.sleep(2)


if __name__ == "__main__":
    run()
