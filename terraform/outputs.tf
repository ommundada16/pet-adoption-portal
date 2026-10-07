# Printed after "terraform apply" finishes
output "public_ip" {
  description = "Fixed public IP of the server - use it as the EC2_HOST secret in GitHub and in ansible/inventory.ini"
  value       = aws_eip.pet_adoption_ip.public_ip
}

output "app_url" {
  description = "Where the website lives"
  value       = "http://${aws_eip.pet_adoption_ip.public_ip}"
}

output "grafana_url" {
  description = "Monitoring dashboards (login admin / the GRAFANA_ADMIN_PASSWORD secret)"
  value       = "http://${aws_eip.pet_adoption_ip.public_ip}:3000"
}
