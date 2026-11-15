from comic_helper import nachtragen
from comic_helper.config import load_pricing

from .test_flow import env, review_form, to_shop  # noqa: F401  (fixtures/helpers)

CFG = load_pricing()


def shop_of(env):
    from comic_helper.shopify import Shopify
    import httpx2
    return Shopify("test.myshopify.com", "tok", "2026-07", "1", transport=httpx2.MockTransport(env.shop))


def test_liste_zeigt_produkte_und_vorhandenen_inhalt(env):  # noqa: F811
    to_shop(env, inhalt="Schon da.")
    rows = nachtragen.list_products(shop_of(env))
    assert rows == [{"handle": "asterix-12-ehapa", "title": rows[0]["title"], "inhalt": "Schon da."}]


def test_plan_unterscheidet_setzen_vorhanden_unbekannt_ungueltig(env):  # noqa: F811
    to_shop(env)                                    # asterix-12-ehapa: no text yet
    to_shop(env, inhalt="Alt.", ausgabe="13")       # asterix-13-ehapa: has text
    texts = {"asterix-12-ehapa": "Ein neuer Text.", "asterix-13-ehapa": "Ersatz.",
             "gibt-es-nicht": "Text.", "asterix-14-ehapa": "Ein <b>Text</b>"}
    status = {p["handle"]: p["status"] for p in nachtragen.plan(shop_of(env), texts, CFG)}
    assert status == {"asterix-12-ehapa": "setzen", "asterix-13-ehapa": "vorhanden",
                      "gibt-es-nicht": "unbekannt", "asterix-14-ehapa": "unbekannt"}


def test_plan_lehnt_ungueltigen_text_ab(env):  # noqa: F811
    to_shop(env)
    (p,) = nachtragen.plan(shop_of(env), {"asterix-12-ehapa": "x" * 601}, CFG)
    assert p["status"] == "ungueltig" and "600" in p["grund"]
    (p,) = nachtragen.plan(shop_of(env), {"asterix-12-ehapa": "Mehr auf https://example.com"}, CFG)
    assert p["status"] == "ungueltig"


def test_trockenlauf_schreibt_nichts_schreiben_setzt_nur_leere(env):  # noqa: F811
    to_shop(env)
    shop = shop_of(env)
    plan = nachtragen.plan(shop, {"asterix-12-ehapa": "Ein neuer Text."}, CFG)
    assert "metafieldsSet" not in env.shop.calls
    results = nachtragen.apply(shop, plan)
    assert results == [{"handle": "asterix-12-ehapa", "ergebnis": "gesetzt"}]
    pid = env.shop.products["asterix-12-ehapa"]["id"]
    assert env.shop.metafields[pid]["value"] == "Ein neuer Text."
    again = nachtragen.apply(shop, nachtragen.plan(shop, {"asterix-12-ehapa": "Noch einer."}, CFG))
    assert again == [] and env.shop.metafields[pid]["value"] == "Ein neuer Text."
