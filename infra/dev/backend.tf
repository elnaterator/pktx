terraform {
  backend "s3" {
    bucket  = "pktx-terraform-state-dev"
    key     = "dev/terraform.tfstate"
    region  = "us-west-2"
    encrypt = true
    # S3 native state locking (<key>.tflock); no DynamoDB table.
    use_lockfile = true
  }
}
