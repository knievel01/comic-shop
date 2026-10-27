"""Shopify Admin GraphQL: one product per title/issue/publisher, one variant per physical copy.

Options: "Zustand" (e.g. "1 – sehr gut") and "Exemplar" (a, b, c, ...). Every variant has
quantity 1 and a unique SKU ending in the copy's short id, so the sales webhook can find
the scan in S3 by prefix listing.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from string import ascii_lowercase

import httpx2

from . import pricing


class ShopifyError(Exception):
    pass


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


def make_sku(titel: str, ausgabe: str, zustand: int, short: str) -> str:
    issue = slugify(ausgabe, 15) if ausgabe and ausgabe != "-" else "x"
    return f"{slugify(titel, 30) or 'comic'}-{issue}-z{zustand}-{short}"


def short_id_from_sku(sku: str) -> str | None:
    m = re.search(r"-([0-9a-f]{12})$", sku or "")
    return m.group(1) if m else None


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
        "<p>Jede Variante ist ein einzelnes, von uns gescanntes Exemplar. "
        "Die Bilder zeigen genau das Heft, das Sie erhalten.</p>"
        f"<p><strong>Unsere Zustandsstufen</strong></p><ul>{zust}</ul>"
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

PUBLISH = """
mutation($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) { userErrors { field message } }
}"""


class Shopify:
    def __init__(self, domain: str, token: str, api_version: str, location_id: str,
                 publication_ids: list[str] | None = None, transport: httpx2.BaseTransport | None = None):
        if not (domain and token and location_id):
            raise ShopifyError("SHOPIFY_SHOP_DOMAIN, SHOPIFY_ADMIN_TOKEN and SHOPIFY_LOCATION_ID are required")
        self.location_id = location_id if location_id.startswith("gid://") else f"gid://shopify/Location/{location_id}"
        self.publication_ids = publication_ids or []
        self.http = httpx2.Client(
            base_url=f"https://{domain}/admin/api/{api_version}",
            headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
            timeout=60,
            transport=transport,
        )

    def gql(self, query: str, variables: dict) -> dict:
        resp = self.http.post("/graphql.json", json={"query": query, "variables": variables})
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

    def add_copy(self, *, copy_short_id: str, proposal: dict, zustand: int, price: float,
                 image_urls: list[str], cfg: dict) -> VariantResult:
        """Idempotent: if a variant with this copy's SKU suffix exists, return it."""
        titel, ausgabe, verlag = proposal["titel"], proposal.get("ausgabe", ""), proposal.get("verlag", "")
        sku = make_sku(titel, ausgabe, zustand, copy_short_id)
        existing = self.find_variant_by_sku(sku)
        if existing:
            ex = next((o["value"] for o in existing["selectedOptions"] if o["name"] == "Exemplar"), "")
            return VariantResult(existing["product"]["id"], existing["id"], sku, ex, created=False)

        handle = product_handle(titel, ausgabe, verlag)
        product = self.gql(PRODUCT_BY_HANDLE, {"handle": handle})["productByIdentifier"]
        zustand_label = pricing.condition_label(zustand, cfg)
        strategy = "DEFAULT"
        if product is None:
            exemplar = "a"
            shop_cfg = cfg.get("shopify", {})
            tags = ["comic", f"comic-key:{handle}"]
            tags += [t for t in (verlag, proposal.get("sprache"), proposal.get("format")) if t]
            created = self._check(self.gql(PRODUCT_CREATE, {"product": {
                "title": product_title(titel, ausgabe, proposal.get("untertitel", ""), verlag),
                "handle": handle,
                "descriptionHtml": description_html(proposal, cfg),
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
                "inventoryQuantities": [{"locationId": self.location_id, "availableQuantity": 1}],
                "mediaSrc": image_urls[:1],
            }],
        })["productVariantsBulkCreate"], "productVariantsBulkCreate")
        variant = result["productVariants"][0]
        return VariantResult(product_id, variant["id"], sku, exemplar, created=True)
