output "eks_cluster_endpoint" {
  description = "Endpoint del clúster EKS"
  value       = module.eks.cluster_endpoint
}

output "ecr_backend_url" {
  description = "URL del repositorio ECR backend"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  description = "URL del repositorio ECR frontend"
  value       = aws_ecr_repository.frontend.repository_url
}

output "rds_endpoint" {
  description = "Endpoint de la base de datos RDS PostgreSQL"
  value       = aws_db_instance.postgres.endpoint
}