"""S3 as the only state store (no comic database).

Layout per copy ("Exemplar", id = UUID from the scan upload):

    eingang/<id>.pdf     scan, status in object tags (status=neu|in-arbeit|offen|bestaetigt|fehler)
    eingang/<id>.json    sidecar: AI proposal, review decision, Shopify ids (mutable working state)
    aktiv/<id>.pdf       confirmed + in Shopify; final metadata on the object
    verkauft/<id>.pdf    sold
    papierkorb/<id>.pdf  deleted in the review UI, restorable (ADR-0019)
    bilder/<id>-1.jpg    cover / bilder/<id>-2.jpg back (for review UI and Shopify media)

Object tags are mutable and cheap, user metadata is not (only via CopyObject with
MetadataDirective=REPLACE), so metadata is written once when the copy moves to aktiv/.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator
from urllib.parse import quote, unquote

from botocore.exceptions import ClientError

EINGANG, AKTIV, VERKAUFT, BILDER = "eingang", "aktiv", "verkauft", "bilder"
PAPIERKORB = "papierkorb"
ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
METADATA_LIMIT = 2048  # bytes, S3 user-defined metadata (keys + values)
SAFE_CHARS = " -_.,:;/()+&'!?#@"


class NotFound(Exception):
    pass


def is_copy_id(value: str) -> bool:
    return bool(ID_RE.match(value))


def short_id(copy_id: str) -> str:
    """12 hex chars, used as SKU suffix. 2^48 space -> collisions negligible at 40k copies."""
    return copy_id.replace("-", "")[:12]


def key_prefix_for_short_id(short: str) -> str:
    return f"{short[:8]}-{short[8:12]}"


def encode_metadata(meta: dict[str, object]) -> dict[str, str]:
    """S3 metadata must be ASCII: URL-encode everything else. Enforces the 2 KB limit."""
    out = {}
    for k, v in meta.items():
        if v is None or v == "":
            continue
        out[k.lower()] = quote(str(v), safe=SAFE_CHARS)
    size = sum(len(k) + len(v) for k, v in out.items())
    if size > METADATA_LIMIT:
        raise ValueError(f"metadata too large ({size} > {METADATA_LIMIT} bytes)")
    return out


def decode_metadata(meta: dict[str, str]) -> dict[str, str]:
    return {k: unquote(v) for k, v in meta.items()}


@dataclass
class ScanObject:
    copy_id: str
    prefix: str
    key: str
    last_modified: datetime


class Store:
    def __init__(self, s3, bucket: str):
        self.s3 = s3
        self.bucket = bucket

    # --- keys ---------------------------------------------------------------
    @staticmethod
    def pdf_key(prefix: str, copy_id: str) -> str:
        return f"{prefix}/{copy_id}.pdf"

    @staticmethod
    def sidecar_key(prefix: str, copy_id: str) -> str:
        return f"{prefix}/{copy_id}.json"

    @staticmethod
    def image_key(copy_id: str, page: int) -> str:
        return f"{BILDER}/{copy_id}-{page}.jpg"

    # --- basic operations -----------------------------------------------------
    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def head(self, key: str) -> dict:
        try:
            return self.s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                raise NotFound(key) from e
            raise

    def get_bytes(self, key: str) -> bytes:
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                raise NotFound(key) from e
            raise

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def put_new_scan(self, copy_id: str, pdf: bytes) -> str:
        """Same contract as comics-scan-sync: never overwrite, tagged status=neu in one call."""
        key = self.pdf_key(EINGANG, copy_id)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=pdf, ContentType="application/pdf",
                           Tagging="status=neu", IfNoneMatch="*")
        return key

    def get_tags(self, key: str) -> dict[str, str]:
        resp = self.s3.get_object_tagging(Bucket=self.bucket, Key=key)
        return {t["Key"]: t["Value"] for t in resp["TagSet"]}

    def put_tags(self, key: str, tags: dict[str, str]) -> None:
        self.s3.put_object_tagging(
            Bucket=self.bucket,
            Key=key,
            Tagging={"TagSet": [{"Key": k, "Value": str(v)} for k, v in sorted(tags.items())]},
        )

    def update_tags(self, key: str, **changes: str) -> dict[str, str]:
        tags = self.get_tags(key)
        for k, v in changes.items():
            if v is None:
                tags.pop(k, None)
            else:
                tags[k] = str(v)
        self.put_tags(key, tags)
        return tags

    def read_json(self, key: str) -> dict:
        return json.loads(self.get_bytes(key))

    def write_json(self, key: str, data: dict) -> None:
        self.put_bytes(key, json.dumps(data, ensure_ascii=False, indent=1).encode(), "application/json")

    def presigned_url(self, key: str, expires: int = 3600) -> str:
        return self.s3.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires
        )

    # --- listing --------------------------------------------------------------
    def list_scans(self, prefix: str, key_prefix: str = "") -> Iterator[ScanObject]:
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=f"{prefix}/{key_prefix}"):
            for obj in page.get("Contents", []):
                name = obj["Key"][len(prefix) + 1 :]
                if "/" in name or not name.endswith(".pdf"):
                    continue  # e.g. eingang/_verify/..., sidecars
                copy_id = name[:-4]
                if is_copy_id(copy_id):
                    yield ScanObject(copy_id, prefix, obj["Key"], obj["LastModified"])

    def locate(self, copy_id: str) -> str:
        """Prefix where the copy currently lives."""
        for prefix in (EINGANG, AKTIV, VERKAUFT):
            if self.exists(self.pdf_key(prefix, copy_id)):
                return prefix
        raise NotFound(copy_id)

    def find_by_short_id(self, short: str, prefixes=(AKTIV, VERKAUFT, EINGANG)) -> tuple[str, str]:
        """(copy_id, prefix) for a SKU suffix. Uses a prefix listing, no full scan."""
        kp = key_prefix_for_short_id(short)
        for prefix in prefixes:
            hits = list(self.list_scans(prefix, kp))
            if len(hits) == 1:
                return hits[0].copy_id, prefix
            if len(hits) > 1:
                raise ValueError(f"ambiguous short id {short}: {[h.copy_id for h in hits]}")
        raise NotFound(short)

    # --- workflow state -------------------------------------------------------
    def claim_new(self, limit: int, stale_after_s: int = 1800, now: float | None = None) -> list[str]:
        """Mark up to `limit` new scans as in-arbeit. Also re-claims scans stuck in-arbeit
        (e.g. crash or n8n restart mid-run), so every scan is processed exactly once in effect."""
        now = now or time.time()
        claimed = []
        for obj in self.list_scans(EINGANG):
            if len(claimed) >= limit:
                break
            tags = self.get_tags(obj.key)
            status = tags.get("status", "neu")
            stale = status == "in-arbeit" and now - float(tags.get("claimed", 0)) > stale_after_s
            if status == "neu" or stale:
                self.update_tags(obj.key, status="in-arbeit", claimed=str(int(now)))
                claimed.append(obj.copy_id)
        return claimed

    def move(
        self,
        copy_id: str,
        src: str,
        dst: str,
        metadata: dict[str, str] | None = None,
        tags: dict[str, str] | None = None,
    ) -> bool:
        """Copy <src>/<id>.pdf (+ sidecar) to <dst>/ and delete the source.

        metadata=None keeps the existing metadata (MetadataDirective=COPY), otherwise REPLACE.
        Idempotent: returns False if the copy is already at dst and gone from src.
        """
        src_key, dst_key = self.pdf_key(src, copy_id), self.pdf_key(dst, copy_id)
        if not self.exists(src_key):
            if self.exists(dst_key):
                return False
            raise NotFound(src_key)
        current_tags = self.get_tags(src_key)
        new_tags = {**current_tags, **(tags or {})}
        args = dict(
            Bucket=self.bucket,
            Key=dst_key,
            CopySource={"Bucket": self.bucket, "Key": src_key},
            TaggingDirective="REPLACE",
            Tagging="&".join(f"{quote(k)}={quote(str(v))}" for k, v in sorted(new_tags.items())),
        )
        if metadata is None:
            args["MetadataDirective"] = "COPY"
        else:
            head = self.head(src_key)
            args.update(
                MetadataDirective="REPLACE",
                Metadata=encode_metadata(metadata),
                ContentType=head.get("ContentType", "application/pdf"),
            )
        self.s3.copy_object(**args)
        src_side, dst_side = self.sidecar_key(src, copy_id), self.sidecar_key(dst, copy_id)
        if self.exists(src_side):
            self.s3.copy_object(Bucket=self.bucket, Key=dst_side, CopySource={"Bucket": self.bucket, "Key": src_side})
            self.s3.delete_object(Bucket=self.bucket, Key=src_side)
        self.s3.delete_object(Bucket=self.bucket, Key=src_key)
        return True
