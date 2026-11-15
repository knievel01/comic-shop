"""One-off helper: add content texts (metafield comic.inhalt) to products that already exist in Shopify (ADR-0012).

Run inside the comic-helper container (credentials are there). The texts come as YAML on stdin
("handle: text"); without --schreiben nothing is changed (dry run). Only empty metafields are set,
hand-written texts stay. Texts follow the same rules as generated ones (length, no HTML or links).

  kubectl -n comics exec deploy/comic-helper -- python -m comic_helper.nachtragen --liste
  kubectl -n comics exec -i deploy/comic-helper -- python -m comic_helper.nachtragen --texte - < texte.yaml
  kubectl -n comics exec -i deploy/comic-helper -- python -m comic_helper.nachtragen --texte - --schreiben < texte.yaml
"""

from __future__ import annotations

import argparse
import sys

import yaml

from .config import pricing_config, settings
from .inhalt import InhaltErgebnis, bereinigen
from .shopify import Shopify

PRODUCTS = """
query($after: String) {
  products(first: 100, after: $after, query: "tag:comic") {
    nodes { id handle title metafield(namespace: "comic", key: "inhalt") { value } }
    pageInfo { hasNextPage endCursor }
  }
}"""


def _products(shop: Shopify) -> list[dict]:
    nodes, after = [], None
    while True:
        page = shop.gql(PRODUCTS, {"after": after})["products"]
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        after = page["pageInfo"]["endCursor"]


def list_products(shop: Shopify) -> list[dict]:
    return [{"handle": p["handle"], "title": p["title"], "inhalt": ((p.get("metafield") or {}).get("value") or "")}
            for p in _products(shop)]


def plan(shop: Shopify, texts: dict[str, str], cfg: dict) -> list[dict]:
    """What would happen per handle: setzen | vorhanden | unbekannt | ungueltig (with reason)."""
    by_handle = {p["handle"]: p for p in _products(shop)}
    out = []
    for handle, text in texts.items():
        text = (text or "").strip()
        product = by_handle.get(handle)
        if product is None:
            out.append({"handle": handle, "status": "unbekannt", "text": text, "grund": "kein Produkt mit diesem Handle"})
        elif ((product.get("metafield") or {}).get("value") or "").strip():
            out.append({"handle": handle, "status": "vorhanden", "text": text, "id": product["id"],
                        "grund": "hat schon einen Inhalt, wird nicht überschrieben"})
        elif bereinigen(InhaltErgebnis(text=text, quelle="wissen", sicherheit=1.0), cfg) is None:
            out.append({"handle": handle, "status": "ungueltig", "text": text, "id": product["id"],
                        "grund": f"leer, länger als {cfg['inhalt']['max_zeichen']} Zeichen oder mit HTML/Link"})
        else:
            out.append({"handle": handle, "status": "setzen", "text": text, "id": product["id"], "grund": ""})
    return out


def apply(shop: Shopify, steps: list[dict]) -> list[dict]:
    """Writes every 'setzen' step; returns [{handle, ergebnis}] (gesetzt | fehler: ...)."""
    return [{"handle": s["handle"], "ergebnis": shop.set_inhalt(s["id"], s["text"], has_inhalt=False)}
            for s in steps if s["status"] == "setzen"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--liste", action="store_true", help="Produkte mit Handle und vorhandenem Inhalt anzeigen")
    ap.add_argument("--texte", metavar="YAML", help="Datei mit 'handle: text' ('-' = stdin)")
    ap.add_argument("--schreiben", action="store_true", help="wirklich nach Shopify schreiben (sonst Trockenlauf)")
    args = ap.parse_args(argv)
    s = settings()
    shop = Shopify(s.shopify_shop_domain, s.shopify_admin_token, s.shopify_api_version, s.shopify_location_id,
                   s.shopify_publication_ids, client_id=s.shopify_client_id, client_secret=s.shopify_client_secret)
    if args.liste:
        for p in list_products(shop):
            print(f"{p['handle']}\t{p['title']}\t{'Inhalt vorhanden' if p['inhalt'] else 'ohne Inhalt'}")
        return 0
    if not args.texte:
        ap.error("--liste oder --texte angeben")
    raw = sys.stdin.read() if args.texte == "-" else open(args.texte, encoding="utf-8").read()
    texts = yaml.safe_load(raw) or {}
    steps = plan(shop, {str(k): str(v) for k, v in texts.items()}, pricing_config())
    for st in steps:
        print(f"[{st['status']}] {st['handle']} {st['grund']}\n    {st['text']}")
    if not args.schreiben:
        print("\nTrockenlauf: nichts geändert. Mit --schreiben wirklich setzen.")
        return 0
    for r in apply(shop, steps):
        print(f"{r['handle']}: {r['ergebnis']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
