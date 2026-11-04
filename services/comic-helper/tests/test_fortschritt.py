import uuid

from .conftest import upload_scan
from .test_flow import H, env  # noqa: F401  (fixture)
from .test_marktpreis import BL, ZV


def tags(env, cid):  # noqa: F811
    return env.store.get_tags(env.store.pdf_key("eingang", cid))


def test_recognition_sets_steps_and_clears_them(env):  # noqa: F811
    env.claude.offers = [(4.0, BL), (6.0, ZV)]
    seen = {}
    parse, search = env.claude.parse, env.claude.search
    c, cid = env.client, str(uuid.uuid4())

    def parse_spy(**kw):
        seen["erkennung"] = dict(tags(env, cid))
        return parse(**kw)

    def search_spy(**kw):
        seen["preissuche"] = dict(tags(env, cid))
        return search(**kw)

    env.claude.beta.messages.parse = parse_spy
    env.claude.messages.create = search_spy
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    assert c.post(f"/api/scans/{cid}/recognize", headers={**H, "X-N8N-Lauf": "1970"}).status_code == 200

    assert seen["erkennung"]["schritt"] == "erkennung" and seen["erkennung"]["lauf"] == "1970"
    assert seen["preissuche"]["schritt"] == "preissuche"
    final = tags(env, cid)
    assert final["status"] == "offen" and "schritt" not in final and "lauf" not in final


def test_progress_endpoint(env):  # noqa: F811
    c, cid, gone = env.client, str(uuid.uuid4()), str(uuid.uuid4())
    upload_scan(env.s3, cid)
    assert c.get(f"/review/fortschritt?ids={cid}").json()[cid] == {
        "status": "neu", "schritt": "", "lauf": "", "seit": None}
    c.post("/api/scans/claim", headers=H)
    env.store.update_tags(env.store.pdf_key("eingang", cid), schritt="erkennung", lauf="7")
    d = c.get(f"/review/fortschritt?ids={cid},{gone}").json()
    assert d[cid]["status"] == "in-arbeit" and d[cid]["schritt"] == "erkennung" and d[cid]["lauf"] == "7"
    assert isinstance(d[cid]["seit"], int)
    assert d[gone] == {"status": "weg"}
    assert c.get("/review/fortschritt?ids=../x").status_code == 400

    page = c.get("/review/").text
    assert f'data-id="{cid}"' in page and 'data-schritt="erkennung"' in page and "KI liest" in page


def test_fail_clears_step(env):  # noqa: F811
    c, cid = env.client, str(uuid.uuid4())
    upload_scan(env.s3, cid)
    c.post("/api/scans/claim", headers=H)
    env.store.update_tags(env.store.pdf_key("eingang", cid), schritt="erkennung", lauf="7")
    assert c.post(f"/api/scans/{cid}/fail", headers=H, json={"fehler": "x"}).status_code == 200
    t = tags(env, cid)
    assert t["status"] == "fehler" and "schritt" not in t and "lauf" not in t
