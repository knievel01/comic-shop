import json
import sys
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
    assert env.s.status()["letzte"][0] == {"name": uuid1, "fotos": 3}


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
            if cmd[0] == "gphoto2":                          # capture: file named after --filename, %C = jpg
                Path(cmd[cmd.index("--filename") + 1].replace("%C", "jpg")).write_bytes(b"raw")
            else:                                            # fswebcam and convert both end with the target path
                Path(cmd[-1]).write_bytes(b"jpg")
            return SimpleNamespace(returncode=0, stdout="")
        return run

    target = tmp_path / "foto-001.jpg"
    assert cp.shoot(str(target), run=run_factory(False)) is True
    assert calls == ["gphoto2", "fswebcam"]
    calls.clear()
    assert cp.shoot(str(target), run=run_factory(True)) is True
    assert calls == ["gphoto2", "gphoto2", "convert"]


def test_aufnahme_meldet_fehler_wenn_kein_bild_entsteht(tmp_path):
    def run(cmd, **kw):
        return SimpleNamespace(returncode=0, stdout="")
    assert cp.shoot(str(tmp_path / "nicht-da.jpg"), run=run) is False


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
