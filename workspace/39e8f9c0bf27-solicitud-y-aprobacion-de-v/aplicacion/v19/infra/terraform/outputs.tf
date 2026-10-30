output "cluster_endpoint" {
  description = "Endpoint privado de la API del clúster EKS."
  value       = module.eks.cluster_endpoint
}

output "cluster_name" {
  description = "Nombre del clúster para configurar kubectl."
  value       = module.eks.cluster_name
}

output "ecr_repository_urls" {
  description = "URLs de los repositorios backend, portal y panel."
  value       = { for name, repository in aws_ecr_repository.applications : name => repository.repository_url }
}

output "rds_endpoint" {
  description = "Endpoint privado de PostgreSQL, incluyendo el puerto."
  value       = aws_db_instance.database.endpoint
}

output "database_secret_arn" {
  description = "ARN del secreto de PostgreSQL; no contiene su valor."
  value       = aws_secretsmanager_secret.database.arn
}

output "vpc_id" {
  description = "Identificador de la VPC."
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Subredes privadas utilizadas por EKS."
  value       = module.vpc.private_subnets
}