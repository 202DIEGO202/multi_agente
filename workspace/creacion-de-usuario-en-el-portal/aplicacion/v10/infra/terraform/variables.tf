variable "region" {
  description = "Región AWS donde se desplegará la infraestructura"
  type        = string
  default     = "us-east-1"
}

variable "nombre" {
  description = "Nombre base para recursos"
  type        = string
  default     = "creacion-usuario-portal"
}

variable "eks_node_count" {
  description = "Número de nodos en el grupo de nodos EKS"
  type        = number
  default     = 3
}

variable "eks_node_instance_type" {
  description = "Tipo de instancia para nodos EKS"
  type        = string
  default     = "t3.medium"
}

variable "rds_instance_class" {
  description = "Clase de instancia para RDS PostgreSQL"
  type        = string
  default     = "db.t3.medium"
}

variable "rds_allocated_storage" {
  description = "Almacenamiento asignado para RDS en GB"
  type        = number
  default     = 20
}

variable "rds_username" {
  description = "Usuario administrador para la base de datos RDS"
  type        = string
  default     = "admin"
}