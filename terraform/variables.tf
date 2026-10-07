variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "instance_type" {
  description = "EC2 instance type. t3.micro (1GB) repeatedly crashed under MySQL+Flask+nginx load (see the post-mortem in the README). The app plus the monitoring stack (Prometheus, Grafana, Loki) needs about 1.5GB, so t3.medium (4GB RAM) is used."
  type        = string
  default     = "t3.medium"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key that will be allowed to log into the VM"
  type        = string
  default     = "~/.ssh/pet-adoption-key.pub"
}

variable "ssh_allowed_cidr" {
  description = "IP range allowed to SSH in. 0.0.0.0/0 means the whole internet (needed so GitHub Actions can deploy); use your own IP/32 if you deploy by hand."
  type        = string
  default     = "0.0.0.0/0"
}
