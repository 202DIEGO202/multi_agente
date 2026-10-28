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

variable "node_group_instance_type" {
  description = "Tipo de instancia para los nodos EKS"
  type        = string
  default     = "t3.medium"
}

variable "node_group_desired_capacity" {
  description = "Cantidad deseada de nodos en el grupo EKS"
  type        = number
  default     = 3
}

variable "node_group_min_capacity" {
  description = "Cantidad mínima de nodos en el grupo EKS"
  type        = number
  default     = 3
}

variable "node_group_max_capacity" {
  description = "Cantidad máxima de nodos en el grupo EKS"
  type        = number
  default     = 3
}

variable "rds_instance_class" {
  description = "Clase de instancia para RDS PostgreSQL"
  type        = string
  default     = "db.t4g.medium"
}

variable "rds_allocated_storage" {
  description = "Almacenamiento asignado para RDS en GB"
  type        = number
  default     = 20
}

variable "rds_username" {
  description = "Usuario administrador para RDS PostgreSQL"
  type        = string
  default     = "admin"
}