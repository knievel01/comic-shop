# --- comics-app: n8n / comic-helper / backup (whole bucket, nothing else) ---
resource "aws_iam_user" "app" {
  name = "comics-app"
}

data "aws_iam_policy_document" "app" {
  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.scans.arn]
  }
  statement {
    sid = "Objects"
    # CopyObject = GetObject on the source + PutObject on the target
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObjectTagging",
      "s3:PutObjectTagging",
      "s3:GetObjectVersion",
    ]
    resources = ["${aws_s3_bucket.scans.arn}/*"]
  }
}

resource "aws_iam_user_policy" "app" {
  name   = "comics-app-bucket"
  user   = aws_iam_user.app.name
  policy = data.aws_iam_policy_document.app.json
}

resource "aws_iam_access_key" "app" {
  user = aws_iam_user.app.name
}

# --- comics-scan-upload: scan station, may only add new objects to eingang/ ---
resource "aws_iam_user" "scan_upload" {
  name = "comics-scan-upload"
}

data "aws_iam_policy_document" "scan_upload" {
  statement {
    sid       = "UploadOnly"
    actions   = ["s3:PutObject", "s3:PutObjectTagging"]
    resources = ["${aws_s3_bucket.scans.arn}/eingang/*"]
  }
}

resource "aws_iam_user_policy" "scan_upload" {
  name   = "comics-scan-upload-eingang"
  user   = aws_iam_user.scan_upload.name
  policy = data.aws_iam_policy_document.scan_upload.json
}

resource "aws_iam_access_key" "scan_upload" {
  user = aws_iam_user.scan_upload.name
}
