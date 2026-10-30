variable "region" {
  description = "Región de AWS"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Entorno lógico"
  type        = string
  default     = "dev"
}

variable "name" {
  description = "Nombre base de recursos"
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

variable "node_instance_type" {
  description = "Tipo de instancia para el node group"
  type        = string
  default     = "t3.medium"
}

variable "node_min_size" {
  description = "Mínimo de nodos"
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Máximo de nodos"
  type        = number
  default     = 4
}

variable "node_desired_size" {
  description = "Deseado de nodos"
  type        = number
  default     = 2
}

variable "db_instance_class" {
  description = "Clase de instancia RDS"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Almacenamiento asignado para RDS"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Nombre inicial de la base de datos"
  type        = string
  default     = "vacaciones"
}

variable "db_username" {
  description = "Usuario administrador de PostgreSQL"
  type        = string
  default     = "appuser"
}

variable "postgres_version" {
  description = "Versión de PostgreSQL"
  type        = string
  default     = "16.3"
}