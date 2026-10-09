variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "tags" {
  type = map(string)
  default = {}
}

variable "writer_role_arn" {
  type = string
}

variable "writer_zip_path" {
  type = string
}
