# Infrastructure Terraform configuration

terraform {
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  required_version = "~> 1.0"
}

provider "aws" {
  region = "ap-southeast-2"

  default_tags {
    tags = {
      env = var.environment_name
      app = "svrmgr"
    }
  }
}
