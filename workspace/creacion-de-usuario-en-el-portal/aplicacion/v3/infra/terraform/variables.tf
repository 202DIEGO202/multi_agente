variable "region" {
  description = "Región AWS donde se desplegará la infraestructura"
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Nombre base para recursos"
  type        = string
  default     = "creacion-usuario-portal"
}

variable "vpc_cidr" {
  description = "CIDR para la VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnets" {
  description = "CIDRs para subredes públicas"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "private_subnets" {
  description = "CIDRs para subredes privadas"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "eks_version" {
  description = "Versión de Kubernetes para EKS"
  type        = string
  default     = "1.27"
}

variable "node_group_desired_capacity" {
  description = "Cantidad deseada de nodos en el grupo"
  type        = number
  default     = 3
}

variable "node_group_max_capacity" {
  description = "Máximo número de nodos en el grupo"
  type        = number
  default     = 5
}

variable "node_group_min_capacity" {
  description = "Mínimo número de nodos en el grupo"
  type        = number
  default     = 1
}

variable "node_group_instance_types" {
  description = "Tipos de instancia para los nodos EKS"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "rds_username" {
  description = "Usuario administrador para la base de datos RDS"
  type        = string
  default     = "admin"
}

variable "rds_engine_version" {
  description = "Versión del motor PostgreSQL para RDS"
  type        = string
  default     = "16.3"
}

variable "rds_instance_class" {
  description = "Clase de instancia para RDS"
  type        = string
  default     = "db.t4g.medium"
}

variable "rds_allocated_storage" {
  description = "Almacenamiento asignado para RDS en GB"
  type        = number
  default     = 20
}