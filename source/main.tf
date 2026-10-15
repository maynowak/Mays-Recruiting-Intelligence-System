terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    local = { source = "hashicorp/local", version = "~> 2.0" }
  }
  backend "local" {
    path = "legacy.tfstate"
  }
}

resource "local_file" "test_resource" {
  filename = "${path.module}/outputs/test.txt"
  content  = "test content"
}
