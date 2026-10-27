variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "bucket_name" {
  description = "Globally unique bucket name, e.g. sepp-comics-scans"
  type        = string
}

variable "noncurrent_version_days" {
  description = "Delete overwritten/deleted object versions after N days"
  type        = number
  default     = 30
}

variable "backup_retention_days" {
  type    = number
  default = 90
}
