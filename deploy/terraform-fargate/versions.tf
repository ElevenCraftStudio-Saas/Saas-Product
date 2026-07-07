terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.40"
    }
  }

  # Uncomment for shared state once the S3 bucket + DynamoDB lock table exist.
  # backend "s3" {
  #   bucket         = "wedfind-tfstate"
  #   key            = "fargate/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "wedfind-tflock"
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "wedfind"
      Environment = var.environment
      Stack       = "fargate"
      ManagedBy   = "terraform"
    }
  }
}
