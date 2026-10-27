import uuid

import pytest

from comic_helper import storage
from comic_helper.storage import AKTIV, EINGANG, VERKAUFT

from .conftest import BUCKET, upload_scan


def new_id():
    return str(uuid.uuid4())


def test_metadata_encoding_roundtrip():
    enc = storage.encode_metadata({"titel": "Fix und Foxi – Größe", "ausgabe": "12", "leer": ""})
    assert all(v.isascii() for v in enc.values())
    assert "leer" not in enc
    assert storage.decode_metadata(enc)["titel"] == "Fix und Foxi – Größe"


def test_metadata_limit():
    with pytest.raises(ValueError):
        storage.encode_metadata({"titel": "ä" * 1000})


def test_short_id_prefix():
    cid = "7f3a9c2b-1234-4abc-8def-0123456789ab"
    assert storage.short_id(cid) == "7f3a9c2b1234"
    assert storage.key_prefix_for_short_id("7f3a9c2b1234") == "7f3a9c2b-1234"


def test_list_ignores_non_scans(s3, store):
    cid = new_id()
    upload_scan(s3, cid)
    s3.put_object(Bucket=BUCKET, Key="eingang/_verify/x.txt", Body=b"x")
    s3.put_object(Bucket=BUCKET, Key="eingang/notauuid.pdf", Body=b"x")
    s3.put_object(Bucket=BUCKET, Key=f"eingang/{cid}.json", Body=b"{}")
    assert [o.copy_id for o in store.list_scans(EINGANG)] == [cid]


def test_claim_exactly_once(s3, store):
    a, b = new_id(), new_id()
    upload_scan(s3, a)
    upload_scan(s3, b)
    first = store.claim_new(limit=10, now=1000)
    assert sorted(first) == sorted([a, b])
    assert store.claim_new(limit=10, now=1100) == []          # already in-arbeit
    assert sorted(store.claim_new(limit=10, now=1000 + 3600)) == sorted([a, b])  # stale -> reclaimed


def test_claim_limit_and_skips_other_status(s3, store):
    ids = [new_id() for _ in range(3)]
    for i in ids:
        upload_scan(s3, i)
    upload_scan(s3, new_id(), tags="status=offen")
    assert len(store.claim_new(limit=2)) == 2
    assert len(store.claim_new(limit=5)) == 1


def test_move_replace_metadata_and_idempotent(s3, store):
    cid = new_id()
    upload_scan(s3, cid)
    store.write_json(store.sidecar_key(EINGANG, cid), {"id": cid})
    assert store.move(cid, EINGANG, AKTIV, metadata={"titel": "Asterix", "zustand": 2}, tags={"status": "aktiv"})
    head = s3.head_object(Bucket=BUCKET, Key=f"aktiv/{cid}.pdf")
    assert head["Metadata"] == {"titel": "Asterix", "zustand": "2"}
    assert head["ContentType"] == "application/pdf"
    assert store.get_tags(f"aktiv/{cid}.pdf")["status"] == "aktiv"
    assert store.exists(f"aktiv/{cid}.json") and not store.exists(f"eingang/{cid}.json")
    assert not store.exists(f"eingang/{cid}.pdf")
    assert store.move(cid, EINGANG, AKTIV) is False                 # second call: no-op
    assert store.locate(cid) == AKTIV


def test_move_copy_keeps_metadata(s3, store):
    cid = new_id()
    upload_scan(s3, cid, prefix=AKTIV)
    store.move(cid, AKTIV, VERKAUFT)
    assert s3.head_object(Bucket=BUCKET, Key=f"verkauft/{cid}.pdf")["Metadata"] == {"exemplar-id": cid}


def test_move_missing_raises(store):
    with pytest.raises(storage.NotFound):
        store.move(new_id(), EINGANG, AKTIV)


def test_find_by_short_id(s3, store):
    cid = new_id()
    upload_scan(s3, cid, prefix=AKTIV)
    assert store.find_by_short_id(storage.short_id(cid)) == (cid, AKTIV)
    with pytest.raises(storage.NotFound):
        store.find_by_short_id("0" * 12)
