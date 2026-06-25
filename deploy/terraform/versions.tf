terraform {
  required_version = ">= 1.6.0" # works with OpenTofu >= 1.6 too

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Remote state — uncomment and fill in once a state bucket exists. Keeping
  # state remote + locked is required for safe multi-operator and prod promotion.
  # backend "s3" {
  #   bucket         = "wedfind-tfstate"
  #   key            = "staging/terraform.tfstate"
  #   region         = "ap-south-1"
  #   dynamodb_table = "wedfind-tflock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "wedfind"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
