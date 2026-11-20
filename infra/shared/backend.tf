terraform {
  backend "s3" {
    bucket  = "pktx-terraform-state-shared"
    key     = "shared/terraform.tfstate"
    region  = "us-west-2"
    encrypt = true
    # S3 native state locking (<key>.tflock); no DynamoDB table.
    use_lockfile = true
  }
}
