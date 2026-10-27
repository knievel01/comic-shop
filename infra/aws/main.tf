resource "aws_s3_bucket" "scans" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "scans" {
  bucket                  = aws_s3_bucket.scans.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "scans" {
  bucket = aws_s3_bucket.scans.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "scans" {
  bucket = aws_s3_bucket.scans.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "scans" {
  bucket = aws_s3_bucket.scans.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "scans" {
  bucket     = aws_s3_bucket.scans.id
  depends_on = [aws_s3_bucket_versioning.scans]

  rule {
    id     = "noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_days
    }
    expiration {
      expired_object_delete_marker = true
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "backup-retention"
    status = "Enabled"
    filter {
      prefix = "backup/"
    }
    expiration {
      days = var.backup_retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = 1
    }
  }

  rule {
    id     = "verify-leftovers"
    status = "Enabled"
    filter {
      prefix = "eingang/_verify/"
    }
    expiration {
      days = 1
    }
  }
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.scans.arn,
      "${aws_s3_bucket.scans.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "scans" {
  bucket     = aws_s3_bucket.scans.id
  policy     = data.aws_iam_policy_document.bucket.json
  depends_on = [aws_s3_bucket_public_access_block.scans]
}
