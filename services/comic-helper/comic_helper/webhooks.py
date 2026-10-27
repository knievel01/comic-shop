"""Shopify order webhooks: sold copies move to verkauft/, cancellations/refunds move back.

Every operation is idempotent (state lives in the object location), so duplicate webhook
deliveries change nothing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone

from . import storage
from .shopify import short_id_from_sku
from .storage import AKTIV, VERKAUFT, Store


def verify_hmac(raw_body: bytes, header_hmac: str, secret: str) -> bool:
    if not secret or not header_hmac:
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), header_hmac.strip())


def _skus_from_order(order: dict) -> list[str]:
    return [li.get("sku") or "" for li in order.get("line_items", [])]


def _skus_from_refund(refund: dict) -> list[str]:
    return [(rli.get("line_item") or {}).get("sku") or "" for rli in refund.get("refund_line_items", [])]


def _move_with_note(store: Store, copy_id: str, src: str, dst: str, note: dict) -> bool:
    key = store.pdf_key(src, copy_id)
    if not store.exists(key):
        return store.move(copy_id, src, dst)  # handles "already moved" / raises NotFound
    meta = storage.decode_metadata(store.head(key).get("Metadata", {}))
    meta.update(note)
    return store.move(copy_id, src, dst, metadata=meta, tags={"status": dst})


def handle(topic: str, payload: dict, store: Store) -> list[dict]:
    """Returns one result entry per line item."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    order_name = str(payload.get("name") or payload.get("order_id") or payload.get("id") or "")
    if topic in ("orders/paid", "orders/create"):
        skus, src, dst = _skus_from_order(payload), AKTIV, VERKAUFT
        note = {"verkauft-am": now, "bestellung": order_name}
    elif topic == "orders/cancelled":
        skus, src, dst = _skus_from_order(payload), VERKAUFT, AKTIV
        note = {"storniert-am": now, "bestellung": order_name}
    elif topic == "refunds/create":
        # Only items that are restocked go back on sale
        restocked = [r for r in payload.get("refund_line_items", []) if r.get("restock_type") in ("return", "cancel")]
        skus, src, dst = _skus_from_refund({"refund_line_items": restocked}), VERKAUFT, AKTIV
        note = {"retoure-am": now, "bestellung": order_name}
    else:
        return [{"status": "ignoriert", "topic": topic}]

    results = []
    for sku in skus:
        short = short_id_from_sku(sku)
        if not short:
            results.append({"sku": sku, "status": "keine-comic-sku"})
            continue
        try:
            copy_id, where = store.find_by_short_id(short, prefixes=(src, dst))
        except storage.NotFound:
            results.append({"sku": sku, "status": "nicht-gefunden"})
            continue
        if where == dst:
            results.append({"sku": sku, "id": copy_id, "status": "bereits-erledigt"})
            continue
        moved = _move_with_note(store, copy_id, src, dst, note)
        results.append({"sku": sku, "id": copy_id, "status": f"nach-{dst}" if moved else "bereits-erledigt"})
    return results
