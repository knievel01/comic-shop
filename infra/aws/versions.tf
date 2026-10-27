terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # State contains the IAM access keys -> keep it local and out of git (see .gitignore),
  # or switch to an encrypted S3 backend in a separate admin account.
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      project = "comic-shop"
      managed = "terraform"
    }
  }
}
