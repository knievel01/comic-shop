import io

import boto3
import pytest
from moto import mock_aws
from PIL import Image, ImageDraw

from comic_helper.storage import Store

BUCKET = "test-comics"


@pytest.fixture
def s3():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-central-1")
        client.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-central-1"})
        client.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
        yield client


@pytest.fixture
def store(s3):
    return Store(s3, BUCKET)


def make_pdf(pages: int = 2) -> bytes:
    images = []
    for i in range(pages):
        im = Image.new("RGB", (600, 850), (240, 200 - i * 50, 80))
        ImageDraw.Draw(im).text((40, 40), f"ASTERIX {12 + i}", fill=(0, 0, 0))
        images.append(im)
    buf = io.BytesIO()
    images[0].save(buf, "PDF", save_all=True, append_images=images[1:], resolution=100)
    return buf.getvalue()


def upload_scan(s3, copy_id: str, pages: int = 2, prefix: str = "eingang", tags: str = "status=neu") -> str:
    key = f"{prefix}/{copy_id}.pdf"
    s3.put_object(Bucket=BUCKET, Key=key, Body=make_pdf(pages), ContentType="application/pdf",
                  Metadata={"exemplar-id": copy_id}, Tagging=tags)
    return key
