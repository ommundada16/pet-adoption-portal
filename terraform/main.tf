terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Automatically finds the latest Ubuntu 22.04 image in whichever region we deploy to,
# instead of hardcoding an AMI ID that's only valid in one specific region
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical (the official publisher of Ubuntu images)

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# Registers our local public key with AWS so we can SSH in - no manual key pair
# creation needed in the console
resource "aws_key_pair" "deployer" {
  key_name   = "pet-adoption-key"
  public_key = file(var.ssh_public_key_path)
}

# Opens the ports we need: 22 (SSH, for Ansible), 80 (website), 3000 (Grafana dashboards).
# Port 5000 (the API) is NOT opened any more - users reach it through nginx on port 80.
# Prometheus (9090) and Alertmanager (9093) stay private too; reach them with an SSH tunnel.
resource "aws_security_group" "allow_web_ssh" {
  name        = "pet-adoption-allow-web-ssh"
  description = "Allow SSH, HTTP, and Grafana traffic"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  ingress {
    description = "Website"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Grafana dashboards"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# The actual virtual machine that will run our Docker containers
resource "aws_instance" "pet_adoption_vm" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.deployer.key_name
  vpc_security_group_ids = [aws_security_group.allow_web_ssh.id]

  # Room for Docker images, the database, and Prometheus/Loki data
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name = "pet-adoption-vm"
  }
}

# An Elastic IP is a fixed public address. Without it the IP changes every time the instance is
# stopped/started, which would break the CI/CD pipeline's deploy target (EC2_HOST secret).
resource "aws_eip" "pet_adoption_ip" {
  instance = aws_instance.pet_adoption_vm.id
  domain   = "vpc"

  tags = {
    Name = "pet-adoption-ip"
  }
}
