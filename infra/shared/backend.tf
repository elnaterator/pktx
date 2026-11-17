terraform {
  backend "s3" {
    bucket         = "pktx-terraform-state-shared"
    key            = "shared/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "pktx-terraform-locks-shared"
    encrypt        = true
  }
}
