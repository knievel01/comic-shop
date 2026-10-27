output "bucket" {
  value = aws_s3_bucket.scans.bucket
}

output "comics_env" {
  description = "Lines for /etc/comics/comics.env – print with: terraform output -raw comics_env"
  sensitive   = true
  value       = <<-EOT
    AWS_REGION=${var.region}
    S3_BUCKET=${aws_s3_bucket.scans.bucket}
    AWS_ACCESS_KEY_ID=${aws_iam_access_key.app.id}
    AWS_SECRET_ACCESS_KEY=${aws_iam_access_key.app.secret}
    SCAN_UPLOAD_AWS_ACCESS_KEY_ID=${aws_iam_access_key.scan_upload.id}
    SCAN_UPLOAD_AWS_SECRET_ACCESS_KEY=${aws_iam_access_key.scan_upload.secret}
  EOT
}
