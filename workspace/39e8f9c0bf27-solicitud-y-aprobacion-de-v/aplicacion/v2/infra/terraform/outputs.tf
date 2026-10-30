output "cluster_endpoint" {
  description = "Endpoint del clúster EKS"
  value       = module.eks.cluster_endpoint
}

output "ecr_backend_url" {
  description = "URL del repositorio ECR backend"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_portal_url" {
  description = "URL del repositorio ECR portal"
  value       = aws_ecr_repository.portal.repository_url
}

output "ecr_panel_url" {
  description = "URL del repositorio ECR panel"
  value       = aws_ecr_repository.panel.repository_url
}

output "rds_endpoint" {
  description = "Endpoint de RDS PostgreSQL"
  value       = aws_db_instance.postgres.endpoint
}