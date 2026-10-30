variable "region" {
  description = "Región de AWS"
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Nombre base del entorno"
  type        = string
  default     = "vacaciones-permisos"
}

variable "vpc_cidr" {
  description = "CIDR de la VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnets" {
  description = "Subredes públicas"
  type        = list(string)
  default     = ["10.20.0.0/24", "10.20.1.0/24"]
}

variable "private_subnets" {
  description = "Subredes privadas"
  type        = list(string)
  default     = ["10.20.10.0/24", "10.20.11.0/24"]
}

variable "eks_version" {
  description = "Versión de Kubernetes para EKS"
  type        = string
  default     = "1.30"
}

variable "node_group_desired_size" {
  description = "Tamaño deseado del node group"
  type        = number
  default     = 2
}

variable "node_group_min_size" {
  description = "Tamaño mínimo del node group"
  type        = number
  default     = 2
}

variable "node_group_max_size" {
  description = "Tamaño máximo del node group"
  type        = number
  default     = 4
}

variable "node_instance_type" {
  description = "Tipo de instancia para los nodos"
  type        = string
  default     = "t3.medium"
}

variable "postgres_version" {
  description = "Versión de PostgreSQL"
  type        = string
  default     = "16.3"
}

variable "rds_instance_class" {
  description = "Clase de instancia RDS"
  type        = string
  default     = "db.t3.medium"
}

variable "rds_allocated_storage" {
  description = "Almacenamiento asignado en GB"
  type        = number
  default     = 20
}

variable "rds_db_name" {
  description = "Nombre de la base de datos"
  type        = string
  default     = "vacaciones"
}

variable "rds_username" {
  description = "Usuario administrador de RDS"
  type        = string
  default     = "appadmin"
}