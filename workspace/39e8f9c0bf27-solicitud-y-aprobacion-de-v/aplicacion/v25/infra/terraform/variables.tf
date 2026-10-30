variable "region" {
  description = "Región AWS de despliegue."
  type        = string
  default     = "eu-west-1"
}

variable "nombre" {
  description = "Nombre del proyecto y prefijo de los recursos."
  type        = string
  default     = "vacaciones-permisos"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,29}$", var.nombre)) && !endswith(var.nombre, "-") && !strcontains(var.nombre, "--")
    error_message = "El nombre debe tener entre 3 y 30 caracteres, empezar con una letra minúscula y usar letras minúsculas, números y guiones, sin guiones consecutivos ni finales."
  }
}

variable "vpc_cidr" {
  description = "CIDR IPv4 de la VPC; se subdivide en redes públicas, privadas y de base de datos."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && can(cidrsubnet(var.vpc_cidr, 8, 22)) && try(tonumber(split("/", var.vpc_cidr)[1]) <= 20, false)
    error_message = "Debe ser un CIDR IPv4 válido con prefijo de red igual o menor que 20."
  }
}

variable "numero_az" {
  description = "Cantidad de zonas de disponibilidad; la región debe disponer de ellas."
  type        = number
  default     = 3

  validation {
    condition     = contains([2, 3], var.numero_az)
    error_message = "Se requieren 2 o 3 zonas de disponibilidad."
  }
}

variable "nat_gateway_unico" {
  description = "Usar un único NAT reduce costes, pero elimina la redundancia por zona."
  type        = bool
  default     = false
}

variable "version_kubernetes" {
  description = "Versión de Kubernetes admitida por EKS en la región elegida."
  type        = string
  default     = "1.33"

  validation {
    condition     = can(regex("^1\.[0-9]+$", var.version_kubernetes))
    error_message = "La versión debe expresarse como 1 seguido de punto y número de versión menor."
  }
}

variable "tipos_instancia_nodos" {
  description = "Tipos de instancia EC2 x86_64 para el node group con Amazon Linux 2023."
  type        = list(string)
  default     = ["m6i.large"]

  validation {
    condition     = length(var.tipos_instancia_nodos) > 0 && alltrue([for tipo in var.tipos_instancia_nodos : length(trimspace(tipo)) > 0])
    error_message = "Debe proporcionarse al menos un tipo de instancia x86_64 no vacío."
  }
}

variable "tamano_node_group" {
  description = "Límites y cantidad inicial de nodos del clúster."
  type = object({
    minimo  = number
    maximo  = number
    deseado = number
  })
  default = {
    minimo  = 2
    maximo  = 4
    deseado = 2
  }

  validation {
    condition = (
      var.tamano_node_group.minimo >= 1 &&
      var.tamano_node_group.minimo <= var.tamano_node_group.deseado &&
      var.tamano_node_group.deseado <= var.tamano_node_group.maximo &&
      alltrue([for valor in values(var.tamano_node_group) : floor(valor) == valor])
    )
    error_message = "Los tamaños deben ser enteros y cumplir 1 <= mínimo <= deseado <= máximo."
  }
}

variable "disco_nodos_gib" {
  description = "Tamaño del disco raíz de cada nodo en GiB."
  type        = number
  default     = 30

  validation {
    condition     = var.disco_nodos_gib >= 20 && floor(var.disco_nodos_gib) == var.disco_nodos_gib
    error_message = "El disco debe tener al menos 20 GiB y un tamaño entero."
  }
}

variable "version_postgresql" {
  description = "Versión de PostgreSQL 16 disponible en RDS; 16 selecciona una versión menor vigente."
  type        = string
  default     = "16"

  validation {
    condition     = can(regex("^16(\.[0-9]+)?$", var.version_postgresql))
    error_message = "La versión debe pertenecer a PostgreSQL 16."
  }
}

variable "clase_instancia_rds" {
  description = "Clase de instancia de RDS compatible con PostgreSQL 16."
  type        = string
  default     = "db.t4g.medium"
}

variable "almacenamiento_rds" {
  description = "Almacenamiento inicial y límite de autoescalado de RDS, en GiB."
  type = object({
    inicial_gib = number
    maximo_gib  = number
  })
  default = {
    inicial_gib = 20
    maximo_gib  = 100
  }

  validation {
    condition = (
      var.almacenamiento_rds.inicial_gib >= 20 &&
      var.almacenamiento_rds.maximo_gib >= ceil(var.almacenamiento_rds.inicial_gib * 1.1) &&
      var.almacenamiento_rds.maximo_gib <= 65536 &&
      alltrue([for valor in values(var.almacenamiento_rds) : floor(valor) == valor])
    )
    error_message = "Los tamaños deben ser enteros: inicial >= 20 GiB y máximo entre el 110% del inicial y 65536 GiB."
  }
}

variable "nombre_base_datos" {
  description = "Nombre inicial de la base de datos PostgreSQL."
  type        = string
  default     = "vacaciones"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{0,62}$", var.nombre_base_datos))
    error_message = "El nombre debe empezar con una letra minúscula y contener hasta 63 letras minúsculas o números."
  }
}

variable "usuario_base_datos" {
  description = "Nombre del usuario maestro de RDS; no contiene la contraseña."
  type        = string
  default     = "vacaciones_admin"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,62}$", var.usuario_base_datos)) && !contains(["postgres", "admin", "root", "rdsadmin"], var.usuario_base_datos)
    error_message = "Use un nombre de hasta 63 caracteres, iniciado por una letra minúscula y distinto de postgres, admin, root y rdsadmin."
  }
}

variable "rds_multi_az" {
  description = "Habilitar réplica de respaldo administrada en otra zona para RDS."
  type        = bool
  default     = true
}

variable "proteccion_eliminacion_rds" {
  description = "Impedir la eliminación accidental de RDS."
  type        = bool
  default     = true
}

variable "retencion_backup_dias" {
  description = "Retención de copias automáticas de RDS."
  type        = number
  default     = 7

  validation {
    condition     = var.retencion_backup_dias >= 1 && var.retencion_backup_dias <= 35 && floor(var.retencion_backup_dias) == var.retencion_backup_dias
    error_message = "La retención debe ser un número entero entre 1 y 35 días."
  }
}

variable "retencion_logs_dias" {
  description = "Retención de los registros de EKS y RDS en CloudWatch."
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.retencion_logs_dias)
    error_message = "La retención debe coincidir con un período admitido por CloudWatch Logs."
  }
}