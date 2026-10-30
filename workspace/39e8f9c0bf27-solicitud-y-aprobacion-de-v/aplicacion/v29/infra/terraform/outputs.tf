output "endpoint_cluster" {
  description = "Endpoint privado de la API de Kubernetes."
  value       = module.eks.cluster_endpoint
}

output "nombre_cluster" {
  description = "Nombre del clúster EKS."
  value       = module.eks.cluster_name
}

output "urls_ecr" {
  description = "URLs de los repositorios de backend, portal y panel."
  value = {
    for nombre, repositorio in aws_ecr_repository.aplicaciones : nombre => repositorio.repository_url
  }
}

output "endpoint_rds" {
  description = "Endpoint privado de PostgreSQL con puerto."
  value       = aws_db_instance.postgres.endpoint
}

output "arn_secreto_rds" {
  description = "ARN del secreto de la contraseña; no expone su contenido."
  value       = aws_secretsmanager_secret.postgres.arn
}