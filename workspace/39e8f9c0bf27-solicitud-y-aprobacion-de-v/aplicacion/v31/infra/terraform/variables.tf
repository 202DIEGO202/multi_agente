variable "region" {
  description = "Región AWS con al menos el número solicitado de zonas disponibles."
  type        = string
  default     = "eu-west-1"

  validation {
    condition     = can(regex("^[a-z]{2}(-[a-z]+)+-[0-9]+$", var.region))
    error_message = "La región debe tener un formato AWS válido."
  }
}

variable "nombre" {
  description = "Nombre base de los recursos."
  type        = string
  default     = "vacaciones"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}[a-z0-9]$", var.nombre))
    error_message = "Usa entre 3 y 32 caracteres: minúsculas, números y guiones, empezando por una letra y terminando en letra o número."
  }
}

variable "numero_az" {
  description = "Número de zonas de disponibilidad para las subredes."
  type        = number
  default     = 2

  validation {
    condition     = contains([2, 3], var.numero_az)
    error_message = "El número de zonas debe ser 2 o 3."
  }
}

variable "version_eks" {
  description = "Versión de Kubernetes disponible en EKS en la región elegida."
  type        = string
  default     = "1.33"

  validation {
    condition     = can(regex("^1\.[0-9]+$", var.version_eks))
    error_message = "La versión debe tener el formato 1.xx."
  }
}

variable "tipos_instancia_nodos" {
  description = "Tipos de instancia x86_64 compatibles con el node group."
  type        = list(string)
  default     = ["t3.medium"]

  validation {
    condition     = length(var.tipos_instancia_nodos) > 0 && alltrue([for tipo in var.tipos_instancia_nodos : length(trimspace(tipo)) > 0])
    error_message = "Indica al menos un tipo de instancia no vacío."
  }
}

variable "nodos_minimos" {
  description = "Cantidad mínima de nodos."
  type        = number
  default     = 2

  validation {
    condition     = var.nodos_minimos >= 1 && floor(var.nodos_minimos) == var.nodos_minimos
    error_message = "La cantidad mínima debe ser un entero positivo."
  }
}

variable "nodos_deseados" {
  description = "Cantidad inicial deseada; debe estar entre el mínimo y el máximo."
  type        = number
  default     = 2

  validation {
    condition     = var.nodos_deseados >= 1 && floor(var.nodos_deseados) == var.nodos_deseados
    error_message = "La cantidad deseada debe ser un entero positivo."
  }
}

variable "nodos_maximos" {
  description = "Cantidad máxima de nodos; debe ser igual o mayor que la deseada."
  type        = number
  default     = 4

  validation {
    condition     = var.nodos_maximos >= 1 && floor(var.nodos_maximos) == var.nodos_maximos
    error_message = "La cantidad máxima debe ser un entero positivo."
  }
}

variable "disco_nodos_gb" {
  description = "Tamaño del disco cifrado de cada nodo, en GiB."
  type        = number
  default     = 50

  validation {
    condition     = var.disco_nodos_gb >= 20 && floor(var.disco_nodos_gb) == var.disco_nodos_gb
    error_message = "El disco debe tener al menos 20 GiB y un tamaño entero."
  }
}

variable "clase_instancia_rds" {
  description = "Clase de instancia compatible con PostgreSQL 16."
  type        = string
  default     = "db.t4g.small"

  validation {
    condition     = can(regex("^db\.[a-z0-9]+\.[a-z0-9]+$", var.clase_instancia_rds))
    error_message = "La clase debe tener el formato db.familia.tamaño."
  }
}

variable "almacenamiento_rds_gb" {
  description = "Almacenamiento inicial RDS, en GiB."
  type        = number
  default     = 20

  validation {
    condition     = var.almacenamiento_rds_gb >= 20 && var.almacenamiento_rds_gb <= 65536 && floor(var.almacenamiento_rds_gb) == var.almacenamiento_rds_gb
    error_message = "El almacenamiento debe ser un entero entre 20 y 65536 GiB."
  }
}

variable "almacenamiento_rds_max_gb" {
  description = "Límite de autoescalado RDS, al menos un 10 % superior al almacenamiento inicial."
  type        = number
  default     = 100

  validation {
    condition     = var.almacenamiento_rds_max_gb >= 22 && var.almacenamiento_rds_max_gb <= 65536 && floor(var.almacenamiento_rds_max_gb) == var.almacenamiento_rds_max_gb
    error_message = "El máximo debe ser un entero entre 22 y 65536 GiB."
  }
}

variable "rds_multi_az" {
  description = "Habilita una réplica de reserva administrada para disponibilidad de RDS."
  type        = bool
  default     = true
}

variable "proteccion_borrado_rds" {
  description = "Protege RDS frente al borrado accidental."
  type        = bool
  default     = true
}

variable "retencion_logs_dias" {
  description = "Retención de los registros del plano de control EKS en CloudWatch."
  type        = number
  default     = 30

  validation {
    condition     = contains([7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.retencion_logs_dias)
    error_message = "Selecciona un período de retención admitido por CloudWatch."
  }
}