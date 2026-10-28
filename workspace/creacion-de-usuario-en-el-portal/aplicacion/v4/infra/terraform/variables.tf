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

variable "eks_node_instance_type" {
  description = "Tipo de instancia para los nodos EKS"
  type        = string
  default     = "t3.medium"
}

variable "eks_node_desired_capacity" {
  description = "Cantidad deseada de nodos en el grupo EKS"
  type        = number
  default     = 3
}

variable "eks_node_min_capacity" {
  description = "Cantidad mínima de nodos en el grupo EKS"
  type        = number
  default     = 1
}

variable "eks_node_max_capacity" {
  description = "Cantidad máxima de nodos en el grupo EKS"
  type        = number
  default     = 5
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

variable "key_name" {
  description = "Nombre de la llave SSH para acceso a nodos EKS"
  type        = string
  default     = ""
}