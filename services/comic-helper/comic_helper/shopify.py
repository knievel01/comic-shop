"""Shopify Admin GraphQL: one product per title/issue/publisher, one variant per physical copy.

Options: "Zustand" (e.g. "1 – sehr gut") and "Exemplar" (a, b, c, ...). Every variant has
quantity 1 and a unique SKU ending in the copy's short id, so a copy in the shop can be traced
back to its scan in S3 (ADR-0013). Sales are handled in Shopify only (ADR-0025).

Lots (ADR-0026): several identical copies, one scan as sample, one variant with quantity n and
Zustand "Sammelposten · Zustand 1–3". The product description then explains what a lot means.
"""

from __future__ import annotations

import html
import re
import threading
import time
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from string import ascii_lowercase

import httpx2

from . import pricing


class ShopifyError(Exception):
    pass


# Dev Dashboard apps have no permanent token: client id + secret are exchanged for a 24 h token (ADR-0021).
# The helper builds a client per request, so the token is cached per process.
_TOKENS: dict[tuple[str, str], tuple[str, float]] = {}
_TOKEN_LOCK = threading.Lock()
_TOKEN_MARGIN_S = 300


def slugify(text: str, max_len: int = 60) -> str:
    text = text.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    text = text.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].strip("-")


def product_handle(titel: str, ausgabe: str, verlag: str) -> str:
    parts = [titel, ausgabe if ausgabe and ausgabe != "-" else "", verlag]
    return slugify(" ".join(p for p in parts if p), 120)


def product_title(titel: str, ausgabe: str, untertitel: str, verlag: str) -> str:
    t = titel
    if ausgabe and ausgabe != "-":
        t += f" {ausgabe}"
    if untertitel:
        t += f" – {untertitel}"
    if verlag:
        t += f" ({verlag})"
    return t


def make_sku(titel: str, ausgabe: str, zustand: int | str, short: str) -> str:
    """zustand: 2 or '1-3' for a lot (pricing.condition_key)."""
    issue = slugify(ausgabe, 15) if ausgabe and ausgabe != "-" else "x"
    return f"{slugify(titel, 30) or 'comic'}-{issue}-z{zustand}-{short}"


def exemplar_label(n: int) -> str:
    """0 -> a, 25 -> z, 26 -> aa, ..."""
    label = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        label = ascii_lowercase[r] + label
    return label


def next_exemplar(existing: set[str]) -> str:
    i = 0
    while exemplar_label(i) in existing:
        i += 1
    return exemplar_label(i)


def description_html(proposal: dict, cfg: dict) -> str:
    rows = [
        ("Verlag", proposal.get("verlag")),
        ("Jahr", proposal.get("jahr")),
        ("Sprache", proposal.get("sprache")),
        ("Format", proposal.get("format")),
        ("EAN/ISBN", proposal.get("ean_isbn")),
    ]
    info = "".join(f"<li><strong>{k}:</strong> {html.escape(str(v))}</li>" for k, v in rows if v)
    zust = "".join(
        f"<li><strong>{html.escape(pricing.condition_label(z, cfg))}:</strong> {html.escape(v['hilfe'])}</li>"
        for z, v in sorted(cfg["zustaende"].items())
    )
    return (
        f"<ul>{info}</ul>"
        "<p>Einzelne Exemplare haben wir selbst gescannt: "
        "Die Bilder zeigen genau das Heft, das Sie erhalten.</p>"
        f"<p><strong>Unsere Zustandsstufen</strong></p><ul>{zust}</ul>"
    )


LOT_MARKER = "Sammelposten:</strong>"


def lot_paragraph(zustaende: Sequence[int], cfg: dict) -> str:
    """Explains lots in the product description (ADR-0026), with this lot as example."""
    label = html.escape(pricing.lot_label(zustaende))
    return (
        f"<p><strong>{LOT_MARKER} Von diesem Heft haben wir mehrere Exemplare. "
        f"Bei der Variante „{label}“ erhalten Sie eines davon in "
        f"{html.escape(pricing.lot_range_words(zustaende, cfg))}, nie schlechter. "
        "Die Bilder dieser Variante zeigen ein Beispielexemplar; Ihr Heft kann davon leicht abweichen.</p>"
    )


@dataclass
class VariantResult:
    product_id: str
    variant_id: str
    sku: str
    exemplar: str
    created: bool


FIND_VARIANT = """
query($q: String!) {
  productVariants(first: 5, query: $q) { nodes { id sku product { id } selectedOptions { name value } } }
}"""

PRODUCT_BY_HANDLE = """
query($handle: String!) {
  productByIdentifier(identifier: {handle: $handle}) {
    id
    descriptionHtml
    variants(first: 250) { nodes { id sku selectedOptions { name value } } }
  }
}"""

PRODUCT_CREATE = """
mutation($product: ProductCreateInput!) {
  productCreate(product: $product) {
    product { id }
    userErrors { field message }
  }
}"""

VARIANTS_CREATE = """
mutation($productId: ID!, $variants: [ProductVariantsBulkInput!]!, $media: [CreateMediaInput!], $strategy: ProductVariantsBulkCreateStrategy) {
  productVariantsBulkCreate(productId: $productId, variants: $variants, media: $media, strategy: $strategy) {
    productVariants { id sku }
    userErrors { field message code }
  }
}"""

PRODUCT_UPDATE = """
mutation($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product { id }
    userErrors { field message }
  }
}"""

PUBLISH = """
mutation($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) { userErrors { field message } }
}"""


class Shopify:
    def __init__(self, domain: str, token: str, api_version: str, location_id: str,
                 publication_ids: list[str] | None = None, transport: httpx2.BaseTransport | None = None,
                 *, client_id: str = "", client_secret: str = ""):
        if not (domain and location_id and (token or (client_id and client_secret))):
            raise ShopifyError("SHOPIFY_SHOP_DOMAIN, SHOPIFY_LOCATION_ID and either SHOPIFY_ADMIN_TOKEN "
                               "or SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET are required")
        self.domain, self.static_token = domain, token
        self.client_id, self.client_secret = client_id, client_secret
        self.location_id = location_id if location_id.startswith("gid://") else f"gid://shopify/Location/{location_id}"
        self.publication_ids = publication_ids or []
        self.http = httpx2.Client(
            base_url=f"https://{domain}/admin/api/{api_version}",
            headers={"Content-Type": "application/json"},
            timeout=60,
            transport=transport,
        )

    def access_token(self, refresh: bool = False) -> str:
        """Static token if configured, otherwise a cached client-credentials token."""
        if self.static_token:
            return self.static_token
        key = (self.domain, self.client_id)
        with _TOKEN_LOCK:
            cached = _TOKENS.get(key)
            if cached and not refresh and cached[1] - _TOKEN_MARGIN_S > time.time():
                return cached[0]
            resp = self.http.post(f"https://{self.domain}/admin/oauth/access_token", headers={"Content-Type": "application/x-www-form-urlencoded"},
                                  data={"grant_type": "client_credentials", "client_id": self.client_id,
                                        "client_secret": self.client_secret})
            if resp.status_code >= 400:
                raise ShopifyError(f"token request failed: HTTP {resp.status_code}")  # body may echo credentials
            body = resp.json()
            _TOKENS[key] = (body["access_token"], time.time() + int(body.get("expires_in", 86399)))
            return _TOKENS[key][0]

    def gql(self, query: str, variables: dict) -> dict:
        payload = {"query": query, "variables": variables}
        resp = self.http.post("/graphql.json", json=payload, headers={"X-Shopify-Access-Token": self.access_token()})
        if resp.status_code == 401 and not self.static_token:  # token revoked or expired early: fetch a new one once
            resp = self.http.post("/graphql.json", json=payload,
                                  headers={"X-Shopify-Access-Token": self.access_token(refresh=True)})
        if resp.status_code >= 400:
            raise ShopifyError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        body = resp.json()
        if body.get("errors"):
            raise ShopifyError(f"GraphQL errors: {body['errors']}")
        return body["data"]

    @staticmethod
    def _check(payload: dict, what: str) -> dict:
        errors = payload.get("userErrors") or []
        if errors:
            raise ShopifyError(f"{what}: {errors}")
        return payload

    def find_variant_by_sku(self, sku: str) -> dict | None:
        nodes = self.gql(FIND_VARIANT, {"q": f"sku:{sku}"})["productVariants"]["nodes"]
        return next((n for n in nodes if n["sku"] == sku), None)

    def add_copy(self, *, copy_short_id: str, proposal: dict, zustand: int | Sequence[int], price: float,
                 image_urls: list[str], cfg: dict, anzahl: int = 1) -> VariantResult:
        """Idempotent: if a variant with this copy's SKU suffix exists, return it.
        anzahl > 1 creates a lot: quantity anzahl, condition range as option value (ADR-0026)."""
        titel, ausgabe, verlag = proposal["titel"], proposal.get("ausgabe", ""), proposal.get("verlag", "")
        zustaende = pricing.condition_range([zustand] if isinstance(zustand, int) else zustand, cfg)
        lot = anzahl > 1
        sku = make_sku(titel, ausgabe, pricing.condition_key(zustaende), copy_short_id)
        existing = self.find_variant_by_sku(sku)
        if existing:
            ex = next((o["value"] for o in existing["selectedOptions"] if o["name"] == "Exemplar"), "")
            return VariantResult(existing["product"]["id"], existing["id"], sku, ex, created=False)

        handle = product_handle(titel, ausgabe, verlag)
        product = self.gql(PRODUCT_BY_HANDLE, {"handle": handle})["productByIdentifier"]
        zustand_label = pricing.lot_label(zustaende) if lot else pricing.condition_label(zustaende[0], cfg)
        strategy = "DEFAULT"
        if product is None:
            exemplar = "a"
            shop_cfg = cfg.get("shopify", {})
            tags = ["comic", f"comic-key:{handle}"]
            tags += [t for t in (verlag, proposal.get("sprache"), proposal.get("format")) if t]
            created = self._check(self.gql(PRODUCT_CREATE, {"product": {
                "title": product_title(titel, ausgabe, proposal.get("untertitel", ""), verlag),
                "handle": handle,
                "descriptionHtml": description_html(proposal, cfg) + (lot_paragraph(zustaende, cfg) if lot else ""),
                "vendor": verlag if shop_cfg.get("hersteller_aus_verlag", True) else None,
                "productType": shop_cfg.get("produkt_typ", "Comic"),
                "status": shop_cfg.get("produkt_status", "ACTIVE"),
                "tags": tags,
                "productOptions": [
                    {"name": "Zustand", "values": [{"name": zustand_label}]},
                    {"name": "Exemplar", "values": [{"name": exemplar}]},
                ],
            }})["productCreate"], "productCreate")
            product_id = created["product"]["id"]
            # productCreate adds a placeholder variant with these option values; replace it
            strategy = "REMOVE_STANDALONE_VARIANT"
            if self.publication_ids:
                self._check(self.gql(PUBLISH, {"id": product_id, "input": [
                    {"publicationId": p} for p in self.publication_ids]})["publishablePublish"], "publish")
        else:
            product_id = product["id"]
            used = {
                o["value"]
                for v in product["variants"]["nodes"]
                for o in v["selectedOptions"]
                if o["name"] == "Exemplar"
                and any(x["name"] == "Zustand" and x["value"] == zustand_label for x in v["selectedOptions"])
            }
            exemplar = next_exemplar(used)
            desc = product.get("descriptionHtml") or ""
            if lot and LOT_MARKER not in desc:  # first lot of this title: explain lots, keep manual edits
                self._check(self.gql(PRODUCT_UPDATE, {"product": {
                    "id": product_id, "descriptionHtml": desc + lot_paragraph(zustaende, cfg)}})["productUpdate"],
                    "productUpdate")

        if lot:
            alt = f"{titel} {ausgabe} – Beispielexemplar, {zustand_label}"
        else:
            alt = f"{titel} {ausgabe} – Exemplar {exemplar}, Zustand {zustand_label}"
        media = [{"originalSource": u, "mediaContentType": "IMAGE", "alt": alt} for u in image_urls]
        result = self._check(self.gql(VARIANTS_CREATE, {
            "productId": product_id,
            "strategy": strategy,
            "media": media,
            "variants": [{
                "optionValues": [
                    {"optionName": "Zustand", "name": zustand_label},
                    {"optionName": "Exemplar", "name": exemplar},
                ],
                "price": f"{price:.2f}",
                "inventoryPolicy": "DENY",
                "inventoryItem": {"sku": sku, "tracked": True},
                "inventoryQuantities": [{"locationId": self.location_id, "availableQuantity": anzahl}],
                "mediaSrc": image_urls[:1],
            }],
        })["productVariantsBulkCreate"], "productVariantsBulkCreate")
        variant = result["productVariants"][0]
        return VariantResult(product_id, variant["id"], sku, exemplar, created=True)
