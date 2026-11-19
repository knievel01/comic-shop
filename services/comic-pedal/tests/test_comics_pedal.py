import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import comics_pedal as cp  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_session(tmp_path, shoot_ok=True, idle=300):
    events, pdfs, clock = [], [], Clock()
    shots = []

    def shoot(path):
        shots.append(path)
        if shoot_ok:
            Path(path).write_bytes(b"jpg")
        return shoot_ok

    def make_pdf(first, last, out):
        pdfs.append((Path(first).name, Path(last).name))
        Path(out).write_bytes(b"%PDF")

    s = cp.Session(tmp_path, shoot=shoot, make_pdf=make_pdf, notify=lambda e: events.append(e), clock=clock,
                   idle_close_s=idle)
    return SimpleNamespace(s=s, events=events, pdfs=pdfs, clock=clock, shots=shots, base=tmp_path)


def folders(env):
    return sorted(p.name for p in (env.base / "erfassung").iterdir())


def test_neues_heft_legt_uuid_ordner_an_und_nutzt_leeren_wieder(tmp_path):
    env = make_session(tmp_path)
    env.s.press_new()
    first = folders(env)
    assert len(first) == 1 and cp.UUID_RE.fullmatch(first[0])
    env.s.press_new()
    assert folders(env) == first and env.events == ["neu", "neu"]


def test_foto_ohne_ordner_gibt_fehler_und_legt_nichts_an(tmp_path):
    env = make_session(tmp_path)
    env.s.press_photo()
    assert env.events == ["fehler"] and env.shots == []
    assert not (env.base / "erfassung").exists() or folders(env) == []


def test_fotos_werden_durchnummeriert_und_fehlgeschlagene_zaehlen_nicht(tmp_path):
    env = make_session(tmp_path)
    env.s.press_new()
    env.s.press_photo()
    env.s.press_photo()
    folder = env.base / "erfassung" / folders(env)[0]
    assert sorted(p.name for p in folder.iterdir()) == ["foto-001.jpg", "foto-002.jpg"]
    bad = make_session(tmp_path / "x", shoot_ok=False)
    bad.s.press_new()
    bad.s.press_photo()
    assert bad.s.status()["fotos"] == 0 and bad.events[-1] == "fehler"


def test_naechstes_heft_schliesst_und_baut_pdf_aus_erstem_und_letztem_foto(tmp_path):
    env = make_session(tmp_path)
    env.s.press_new()
    uuid1 = folders(env)[0]
    for _ in range(3):
        env.s.press_photo()
    env.s.press_new()
    assert env.pdfs == [("foto-001.jpg", "foto-003.jpg")]
    assert (env.base / "neu" / f"{uuid1}.pdf").read_bytes() == b"%PDF"
    assert not list((env.base / "neu").glob("*.part"))          # no half-written file is left behind
    assert (env.base / "erfassung" / uuid1).is_dir()            # the folder stays until it is renamed
    assert len(folders(env)) == 2 and "zu" in env.events
    h = env.s.status()["hefte"][0]
    assert h["name"] == uuid1 and h["fotos"] == 3 and h["fehler"] is None and h["zu"] > 0


def test_ordner_mit_einem_foto_geht_nach_fehler(tmp_path):
    env = make_session(tmp_path)
    env.s.press_new()
    uuid1 = folders(env)[0]
    env.s.press_photo()
    env.s.press_new()
    assert (env.base / "fehler" / uuid1).is_dir() and env.pdfs == []
    assert "fehler" in env.events


def test_ruhezeit_schliesst_den_ordner_und_loescht_leere(tmp_path):
    env = make_session(tmp_path, idle=300)
    env.s.press_new()
    uuid1 = folders(env)[0]
    env.s.press_photo()
    env.s.press_photo()
    env.clock.t += 299
    env.s.tick()
    assert env.pdfs == []                                        # not yet
    env.clock.t += 2
    env.s.tick()
    assert env.pdfs and (env.base / "neu" / f"{uuid1}.pdf").exists() and env.s.status()["heft"] is None
    env.s.press_new()                                            # empty folder, nobody shoots
    env.clock.t += 301
    env.s.tick()
    assert env.s.status()["heft"] is None and folders(env) == [uuid1]


def test_status_sagt_was_als_naechstes_kommt(tmp_path):
    env = make_session(tmp_path)
    assert "neues Heft" in env.s.status()["naechstes"]
    env.s.press_new()
    assert "Cover" in env.s.status()["naechstes"]
    env.s.press_photo()
    assert "Rückseite" in env.s.status()["naechstes"] and env.s.status()["fotos"] == 1


def test_entprellen_ignoriert_zweiten_druck_innerhalb_der_sperrzeit():
    clock = Clock()
    d = cp.Debounce(0.4, clock)
    assert d.ok("a") and not d.ok("a")
    clock.t += 0.5
    assert d.ok("a")
    assert d.ok("b")                                             # every switch has its own timer


def test_einrichtung_ordnet_schalter_nach_usb_port_zu():
    c = cp.Calibrator()
    assert c.next_prompt() == "schalter1"
    assert c.feed("usb-0000:00:14.0-2") is False
    assert c.next_prompt() == "schalter2"
    assert c.feed("usb-0000:00:14.0-2") is False                 # same pedal again does not count
    assert c.feed("usb-0000:00:14.0-3") is True
    assert c.result() == {"schalter1": "usb-0000:00:14.0-2", "schalter2": "usb-0000:00:14.0-3"}


def test_geraetegruppe_aus_phys_ohne_interface():
    assert cp.group_key("usb-0000:00:14.0-2/input0") == "usb-0000:00:14.0-2"
    assert cp.group_key("usb-0000:00:14.0-2.4/input2") == "usb-0000:00:14.0-2.4"


def test_aufnahme_nimmt_canon_wenn_erkannt_sonst_webcam(tmp_path):
    calls = []

    def run_factory(canon):
        def run(cmd, **kw):
            calls.append(cmd[0])
            if cmd[0] == "gphoto2" and "--auto-detect" in cmd:
                out = "Model  Port\n-----\n" + ("Canon EOS  usb:001,004\n" if canon else "")
                return SimpleNamespace(returncode=0, stdout=out)
            if cmd[0] == "gphoto2" and "--set-config" in cmd:
                return SimpleNamespace(returncode=0, stdout="")
            if cmd[0] == "gphoto2":                          # capture: file named after --filename, %C = jpg
                Path(cmd[cmd.index("--filename") + 1].replace("%C", "jpg")).write_bytes(b"raw")
            else:                                            # fswebcam and convert both end with the target path
                Path(cmd[-1]).write_bytes(b"jpg")
            return SimpleNamespace(returncode=0, stdout="")
        return run

    target = tmp_path / "foto-001.jpg"
    assert cp.shoot(str(target), run=run_factory(False)) == "Webcam"
    assert calls == ["gphoto2", "fswebcam"]
    calls.clear()
    assert cp.shoot(str(target), run=run_factory(True)) == "Canon"
    assert calls == ["gphoto2", "gphoto2", "gphoto2"]                   # no conversion: the camera sends the size


def canon_run(seen, ext="jpg", capture_fails=False, no_file=False, cwds=None):
    def run(cmd, **kw):
        seen.append(cmd)
        if cwds is not None and cmd[0] == "gphoto2":
            cwds.append(kw.get("cwd"))
        if cmd[0] == "gphoto2" and "--auto-detect" in cmd:
            return SimpleNamespace(returncode=0, stdout="Model  Port\n-----\nCanon EOS 450D (PTP mode)  usb:001,004\n")
        if cmd[0] == "gphoto2" and "--capture-image-and-download" in cmd:
            if capture_fails:
                raise cp.subprocess.CalledProcessError(1, cmd)
            if no_file:                                  # gphoto2 exits 0 although the download failed
                return SimpleNamespace(returncode=0, stdout="")
            Path(cmd[cmd.index("--filename") + 1].replace("%C", ext)).write_bytes(b"raw")
        elif cmd[0] == "convert":
            Path(cmd[-1]).write_bytes(b"jpg")
        return SimpleNamespace(returncode=0, stdout="")
    return run


def test_canon_speichert_auf_die_sd_karte(tmp_path):
    seen = []
    assert cp.shoot(str(tmp_path / "f.jpg"), run=canon_run(seen)) == "Canon"
    target = next(c for c in seen if "--set-config" in c)
    assert "capturetarget=1" in target and f"imageformat={cp.CANON_FORMAT}" in target
    assert not any(c[0] == "convert" for c in seen)
    assert (tmp_path / "f.jpg").read_bytes() == b"raw"          # the camera's JPEG, moved as it is
    assert seen.index(target) < next(i for i, c in enumerate(seen) if "--capture-image-and-download" in c)


def test_canon_auf_raw_gibt_klaren_hinweis(tmp_path):
    seen = []
    try:
        cp.shoot(str(tmp_path / "f.jpg"), run=canon_run(seen, ext="cr2"))
        raise AssertionError("expected CameraHint")
    except cp.CameraHint as e:
        assert "JPEG" in str(e)
    assert not any(c[0] == "convert" for c in seen)


def test_canon_fehler_nimmt_nicht_die_webcam(tmp_path):
    seen = []
    assert cp.shoot(str(tmp_path / "f.jpg"), run=canon_run(seen, capture_fails=True)) is None
    assert not any(c[0] == "fswebcam" for c in seen)


def test_hinweis_der_kamera_steht_im_status_bis_zum_naechsten_guten_foto(tmp_path):
    env = make_session(tmp_path)
    answers = iter([cp.CameraHint("Kamera auf JPEG stellen"), True])

    def shoot(path):
        a = next(answers)
        if isinstance(a, Exception):
            raise a
        Path(path).write_bytes(b"jpg")
        return True

    env.s.shoot = shoot
    env.s.press_new()
    env.s.press_photo()
    assert env.s.status()["hinweis"] == "Kamera auf JPEG stellen" and env.events[-1] == "fehler"
    assert env.s.status()["fotos"] == 0
    env.s.press_photo()
    assert env.s.status()["hinweis"] is None and env.s.status()["fotos"] == 1


def test_aufnahme_meldet_fehler_wenn_kein_bild_entsteht(tmp_path):
    def run(cmd, **kw):
        return SimpleNamespace(returncode=0, stdout="")
    assert cp.shoot(str(tmp_path / "nicht-da.jpg"), run=run) is None


def test_pdf_wird_mit_img2pdf_aus_zwei_bildern_gebaut(tmp_path):
    seen = []
    cp.build_pdf("a.jpg", "b.jpg", str(tmp_path / "x.pdf.part"), run=lambda cmd, **kw: seen.append(cmd) or SimpleNamespace(returncode=0))
    assert seen[0][:3] == ["img2pdf", "a.jpg", "b.jpg"] and seen[0][-1].endswith("x.pdf.part")


def test_status_server_antwortet_mit_json_und_cors(tmp_path):
    env = make_session(tmp_path)
    server = cp.start_status_server(env.s, port=0)
    try:
        port = server.server_address[1]
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}/status.json", timeout=5)
        assert json.load(r)["heft"] is None
        assert r.headers["Access-Control-Allow-Origin"] == "*"
        pre = urllib.request.Request(f"http://127.0.0.1:{port}/status.json", method="OPTIONS")
        assert urllib.request.urlopen(pre, timeout=5).headers["Access-Control-Allow-Private-Network"] == "true"
    finally:
        server.shutdown()


def ev(t, value=1, type_=1):
    return SimpleNamespace(type=type_, value=value, timestamp=lambda: t)


def test_jeder_tritt_zaehlt_auch_mehrere_in_einem_lesedurchgang():
    batch = [("s2", [ev(10.0), ev(10.1, value=0), ev(10.5), ev(10.6, value=0)])]
    assert cp.extract_presses(batch) == [("s2", 10.0), ("s2", 10.5)]


def test_presses_werden_zeitlich_sortiert_und_nur_tastendruecke_zaehlen():
    batch = [("s2", [ev(11.0), ev(11.0, type_=2)]), ("s1", [ev(10.0), ev(10.0, value=2)])]
    assert cp.extract_presses(batch) == [("s1", 10.0), ("s2", 11.0)]


def test_entprellen_nach_ereigniszeit_doppelte_meldung_derselben_betaetigung_faellt_weg():
    d = cp.Debounce()
    assert cp.DEBOUNCE_S <= 0.25
    assert d.ok("s2", 10.000) and not d.ok("s2", 10.005)   # same press reported by keyboard and mouse node
    assert d.ok("s2", 10.300)                              # a quick second tap is a second photo


def test_gphoto2_laeuft_im_temp_ordner_weil_der_dienst_in_wurzel_nicht_schreiben_darf(tmp_path):
    seen, cwds = [], []
    cp.shoot(str(tmp_path / "f.jpg"), run=canon_run(seen, cwds=cwds))
    capture = [c for c in seen if c[0] == "gphoto2" and "--auto-detect" not in c]
    assert cwds[-len(capture):] and all(c and c != "/" and "comics-pedal-" in c for c in cwds[-len(capture):])


def test_ausgeloest_aber_kein_bild_gibt_hinweis(tmp_path):
    try:
        cp.shoot(str(tmp_path / "f.jpg"), run=canon_run([], no_file=True))
        raise AssertionError("expected CameraHint")
    except cp.CameraHint as e:
        assert "kam nicht an" in str(e)


def test_status_zeigt_kamera_schalter_und_bilder_des_hefts(tmp_path):
    env = make_session(tmp_path)
    env.s.shoot = lambda path: Path(path).write_bytes(b"jpg") and "Canon"
    st = env.s.status()
    assert st["schalter"] == "fehlen" and st["hefte"] == [] and st["kamera"] is None and st["aufnahme"] is False
    env.s.press_new()
    env.s.press_photo()
    env.s.press_photo()
    st = env.s.status()
    assert st["kamera"] == "Canon" and st["fotos"] == 2
    assert env.s.photo(1).name == "foto-001.jpg" and env.s.photo(-1).name == "foto-002.jpg" and env.s.photo(3) is None


def test_alle_hefte_seit_start_neuestes_zuerst_mit_fotos(tmp_path):
    env = make_session(tmp_path)
    names = []
    for fotos in (2, 3, 1):
        env.s.press_new()
        names.append(env.s.status()["heft"])
        for _ in range(fotos):
            env.s.press_photo()
    env.s.close()
    hefte = env.s.status()["hefte"]
    assert [h["name"] for h in hefte] == names[::-1]
    assert [h["fotos"] for h in hefte] == [1, 3, 2] and hefte[0]["fehler"] == "zu_wenig"
    assert env.s.photo(1, names[0]) == env.base / "erfassung" / names[0] / "foto-001.jpg"
    assert env.s.photo(1, names[2]) == env.base / "fehler" / names[2] / "foto-001.jpg"
    assert env.s.photo(1, "00000000-0000-0000-0000-000000000000") is None


def test_bilder_auch_nach_dem_umbenennen_ueber_den_link(tmp_path):
    env = make_session(tmp_path, idle=10)
    env.s.press_new()
    name = folders(env)[0]
    env.s.press_photo()
    env.s.press_photo()
    env.s.close()
    (env.base / "hochgeladen").mkdir()
    target = env.base / "hochgeladen" / "yakari-1-ehapa"
    (env.base / "erfassung" / name).rename(target)              # what comics-folder-rename does
    (env.base / ".umbenannt").mkdir()
    (env.base / ".umbenannt" / name).symlink_to(target)
    assert env.s.photo(-1, name).resolve() == (target / "foto-002.jpg").resolve()


def test_status_antwortet_waehrend_die_kamera_ausloest(tmp_path):
    import threading
    env = make_session(tmp_path)
    started, release = threading.Event(), threading.Event()

    def slow_shoot(path):
        started.set()
        release.wait(5)
        Path(path).write_bytes(b"jpg")
        return "Canon"

    env.s.shoot = slow_shoot
    env.s.press_new()
    t = threading.Thread(target=env.s.press_photo)
    t.start()
    try:
        assert started.wait(5)
        done = []
        reader = threading.Thread(target=lambda: done.append(env.s.status()))
        reader.start()
        reader.join(1)
        assert done and done[0]["aufnahme"] is True and done[0]["fotos"] == 0
    finally:
        release.set()
        t.join(5)
    assert env.s.status()["aufnahme"] is False and env.s.status()["fotos"] == 1


def test_tasten_auf_dem_bildschirm_nur_aus_dem_lan(tmp_path):
    env = make_session(tmp_path)
    server = cp.start_status_server(env.s, port=0)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        def post(path, origin, header=True):
            h = {"Origin": origin} if origin else {}
            if header:
                h["X-Comics-Pedal"] = "1"
            req = urllib.request.Request(url + path, method="POST", headers=h, data=b"")
            try:
                return urllib.request.urlopen(req, timeout=5).status
            except urllib.error.HTTPError as e:
                return e.code
        assert post("/neu", "https://boese.example.com") == 403
        assert post("/neu", "http://192.168.40.120", header=False) == 403
        assert post("/neu", None) == 403
        assert post("/neu", "http://192.168.40.120") == 200 and env.events == ["neu"]
        assert post("/foto", "http://localhost:8080") == 200 and env.s.status()["fotos"] == 1
        img = urllib.request.urlopen(url + "/foto/1.jpg", timeout=5)
        assert img.headers["Content-Type"] == "image/jpeg" and img.read() == b"jpg"
        assert img.headers["Cache-Control"] == "max-age=86400"
        name = env.s.status()["heft"]
        assert urllib.request.urlopen(f"{url}/heft/{name}/foto/1.jpg", timeout=5).read() == b"jpg"
        try:
            urllib.request.urlopen(url + "/foto/9.jpg", timeout=5)
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()
