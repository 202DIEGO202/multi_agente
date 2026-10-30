output "endpoint_cluster" {
  description = "Endpoint privado del API de Kubernetes del clúster EKS."
  value       = module.eks.cluster_endpoint
}

output "nombre_cluster" {
  description = "Nombre del clúster para configurar el acceso con AWS CLI."
  value       = module.eks.cluster_name
}

output "urls_ecr" {
  description = "URLs de los repositorios ECR de backend, portal y panel."
  value       = { for nombre, repositorio in aws_ecr_repository.applications : nombre => repositorio.repository_url }
}

output "endpoint_rds" {
  description = "Endpoint privado de PostgreSQL, incluyendo el puerto."
  value       = aws_db_instance.postgres.endpoint
}

output "arn_secreto_rds" {
  description = "ARN del secreto de conexión; no expone su contenido."
  value       = aws_secretsmanager_secret.postgres.arn
}

output "vpc_id" {
  description = "Identificador de la VPC del proyecto."
  value       = module.vpc.vpc_id
}

output "subredes_privadas" {
  description = "Subredes privadas de los nodos EKS."
  value       = module.vpc.private_subnets
}