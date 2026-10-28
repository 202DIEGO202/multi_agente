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
  default     = 1
}

variable "node_group_max_capacity" {
  description = "Cantidad máxima de nodos en el grupo EKS"
  type        = number
  default     = 4
}

variable "rds_instance_class" {
  description = "Clase de instancia para RDS PostgreSQL"
  type        = string
  default     = "db.t3.medium"
}