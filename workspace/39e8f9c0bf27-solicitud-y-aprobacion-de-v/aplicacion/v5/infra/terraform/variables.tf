variable "region" {
  description = "Región AWS"
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

variable "azs" {
  description = "Zonas de disponibilidad"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
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

variable "database_subnets" {
  description = "Subredes para base de datos"
  type        = list(string)
  default     = ["10.20.20.0/24", "10.20.21.0/24"]
}

variable "eks_version" {
  description = "Versión de Kubernetes para EKS"
  type        = string
  default     = "1.29"
}

variable "node_instance_type" {
  description = "Tipo de instancia para el node group"
  type        = string
  default     = "t3.medium"
}

variable "node_group_min_size" {
  description = "Mínimo de nodos"
  type        = number
  default     = 2
}

variable "node_group_max_size" {
  description = "Máximo de nodos"
  type        = number
  default     = 4
}

variable "node_group_desired_size" {
  description = "Cantidad deseada de nodos"
  type        = number
  default     = 2
}

variable "postgres_version" {
  description = "Versión de PostgreSQL"
  type        = string
  default     = "16.3"
}

variable "db_instance_class" {
  description = "Clase de instancia RDS"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Almacenamiento inicial en GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Nombre de la base de datos"
  type        = string
  default     = "vacaciones"
}

variable "db_username" {
  description = "Usuario administrador de la base de datos"
  type        = string
  default     = "appadmin"
}