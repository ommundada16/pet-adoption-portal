variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "instance_type" {
  description = "EC2 instance type. t3.micro (1GB RAM, free-tier) repeatedly became unresponsive under MySQL+Flask+nginx load - t3.small (2GB RAM) is used instead for demo reliability."
  type        = string
  default     = "t3.small"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key that will be allowed to log into the VM"
  type        = string
  default     = "~/.ssh/pet-adoption-key.pub"
}
