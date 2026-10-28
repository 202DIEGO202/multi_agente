output "eks_cluster_endpoint" {
  description = "Endpoint del clúster EKS"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_certificate_authority_data" {
  description = "Certificado CA del clúster EKS"
  value       = module.eks.cluster_certificate_authority_data
}

output "ecr_backend_url" {
  description = "URL del repositorio ECR para backend"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_portal_url" {
  description = "URL del repositorio ECR para portal"
  value       = aws_ecr_repository.portal.repository_url
}

output "ecr_panel_url" {
  description = "URL del repositorio ECR para panel"
  value       = aws_ecr_repository.panel.repository_url
}

output "rds_endpoint" {
  description = "Endpoint de la base de datos RDS PostgreSQL"
  value       = aws_db_instance.postgresql.endpoint
}

output "rds_secret_arn" {
  description = "ARN del secreto en Secrets Manager para la contraseña RDS"
  value       = aws_secretsmanager_secret.rds_password_secret.arn
}