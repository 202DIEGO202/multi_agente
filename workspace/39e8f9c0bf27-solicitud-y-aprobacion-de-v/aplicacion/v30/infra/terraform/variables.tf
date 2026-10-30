variable "region" {
  description = "Región de AWS para todos los recursos."
  type        = string
  default     = "eu-west-1"
}

variable "nombre" {
  description = "Nombre del proyecto y prefijo de recursos."
  type        = string
  default     = "vacaciones-permisos"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,38}[a-z0-9]$", var.nombre)) && !strcontains(var.nombre, "--")
    error_message = "El nombre debe tener entre 3 y 40 caracteres, comenzar con una letra y contener solo minúsculas, números y guiones no consecutivos, sin guion final."
  }
}

variable "vpc_cidr" {
  description = "Bloque IPv4 de la VPC; se reservan subredes mediante ocho bits adicionales."
  type        = string
  default     = "10.40.0.0/16"

  validation {
    condition = can(cidrnetmask(var.vpc_cidr)) && can(regex("/(16|17|18|19|20)$", var.vpc_cidr))
    error_message = "Debe ser un CIDR IPv4 con prefijo entre /16 y /20."
  }
}

variable "numero_zonas" {
  description = "Número de zonas de disponibilidad; la región debe disponer de ellas."
  type        = number
  default     = 3

  validation {
    condition     = contains([2, 3], var.numero_zonas)
    error_message = "El número de zonas debe ser 2 o 3."
  }
}

variable "version_eks" {
  description = "Versión de Kubernetes admitida por EKS en la región seleccionada."
  type        = string
  default     = "1.33"

  validation {
    condition     = can(regex("^1\.[0-9]+$", var.version_eks))
    error_message = "La versión debe tener formato 1.xx."
  }
}

variable "tamanos_nodos" {
  description = "Capacidad del node group; los tipos de instancia deben ser x86_64."
  type = object({
    tipos_instancia = list(string)
    minimo          = number
    deseado         = number
    maximo          = number
    disco_gib       = number
  })
  default = {
    tipos_instancia = ["t3.large"]
    minimo          = 2
    deseado         = 3
    maximo          = 6
    disco_gib       = 40
  }

  validation {
    condition = (
      length(var.tamanos_nodos.tipos_instancia) > 0 &&
      var.tamanos_nodos.minimo >= 1 &&
      var.tamanos_nodos.minimo <= var.tamanos_nodos.deseado &&
      var.tamanos_nodos.deseado <= var.tamanos_nodos.maximo &&
      var.tamanos_nodos.disco_gib >= 20 &&
      floor(var.tamanos_nodos.minimo) == var.tamanos_nodos.minimo &&
      floor(var.tamanos_nodos.deseado) == var.tamanos_nodos.deseado &&
      floor(var.tamanos_nodos.maximo) == var.tamanos_nodos.maximo &&
      floor(var.tamanos_nodos.disco_gib) == var.tamanos_nodos.disco_gib
    )
    error_message = "Indica tipos de instancia, cantidades enteras con 1 <= mínimo <= deseado <= máximo y un disco entero de al menos 20 GiB."
  }
}

variable "tamanos_rds" {
  description = "Clase de RDS y límites del almacenamiento gp3."
  type = object({
    clase_instancia            = string
    almacenamiento_gib        = number
    almacenamiento_maximo_gib = number
  })
  default = {
    clase_instancia            = "db.t4g.medium"
    almacenamiento_gib        = 30
    almacenamiento_maximo_gib = 150
  }

  validation {
    condition = (
      startswith(var.tamanos_rds.clase_instancia, "db.") &&
      var.tamanos_rds.almacenamiento_gib >= 20 &&
      var.tamanos_rds.almacenamiento_maximo_gib >= ceil(var.tamanos_rds.almacenamiento_gib * 1.1) &&
      var.tamanos_rds.almacenamiento_maximo_gib <= 65536 &&
      floor(var.tamanos_rds.almacenamiento_gib) == var.tamanos_rds.almacenamiento_gib &&
      floor(var.tamanos_rds.almacenamiento_maximo_gib) == var.tamanos_rds.almacenamiento_maximo_gib
    )
    error_message = "Usa una clase db.*, almacenamiento entero de al menos 20 GiB y un máximo entero al menos 10% superior, sin superar 65536 GiB."
  }
}

variable "rds_multi_az" {
  description = "Activa una réplica en espera administrada por RDS para alta disponibilidad."
  type        = bool
  default     = true
}