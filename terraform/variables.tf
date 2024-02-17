variable "aws_region" {
  description = "Name of AWS region to put resources in"
  type        = string
}

variable "discord_public_key" {
  description = "Discord app public key"
  sensitive   = true
  type        = string
}

variable "environment_name" {
  default     = "dev"
  description = "Environment short-name"
  type        = string
}
