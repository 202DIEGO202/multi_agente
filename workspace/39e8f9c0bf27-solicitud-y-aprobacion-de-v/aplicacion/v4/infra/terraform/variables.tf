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

variable "eks_version" {
  description = "Versión de Kubernetes para EKS"
  type        = string
  default     = "1.31"
}

variable "node_instance_type" {
  description = "Tipo de instancia para el node group"
  type        = string
  default     = "t3.medium"
}

variable "node_desired_size" {
  description = "Deseado del node group"
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Mínimo del node group"
  type        = number
  default     = 2
}

variable "node_max_size" {
  description = "Máximo del node group"
  type        = number
  default     = 4
}

variable "db_instance_class" {
  description = "Clase de instancia RDS"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Almacenamiento RDS en GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Nombre de la base de datos"
  type        = string
  default     = "vacaciones"
}

variable "db_username" {
  description = "Usuario administrador de PostgreSQL"
  type        = string
  default     = "appadmin"
}