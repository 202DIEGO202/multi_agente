variable "region" {
  description = "Región de AWS."
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Nombre común de los recursos del proyecto."
  type        = string
  default     = "vacaciones-permisos"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,31}$", var.name)) && !endswith(var.name, "-") && !strcontains(var.name, "--")
    error_message = "El nombre debe tener entre 3 y 32 caracteres, empezar con una letra y usar minúsculas, números y guiones sin guiones dobles ni finales."
  }
}

variable "vpc_cidr" {
  description = "CIDR IPv4 de la VPC; se subdivide en redes públicas, privadas y de base de datos."
  type        = string
  default     = "10.40.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && try(tonumber(split("/", var.vpc_cidr)[1]) >= 16 && tonumber(split("/", var.vpc_cidr)[1]) <= 20, false)
    error_message = "Indique un CIDR IPv4 válido con prefijo entre /16 y /20."
  }
}

variable "availability_zone_count" {
  description = "Número de zonas de disponibilidad."
  type        = number
  default     = 3

  validation {
    condition     = contains([2, 3], var.availability_zone_count)
    error_message = "Deben utilizarse dos o tres zonas de disponibilidad."
  }
}

variable "kubernetes_version" {
  description = "Versión de Kubernetes disponible en EKS en la región seleccionada."
  type        = string
  default     = "1.34"

  validation {
    condition     = can(regex("^1\\.[0-9]+$", var.kubernetes_version))
    error_message = "La versión debe usar el formato 1.xx."
  }
}

variable "node_instance_types" {
  description = "Tipos de instancia x86_64 para el grupo de nodos EKS."
  type        = list(string)
  default     = ["t3.large"]

  validation {
    condition     = length(var.node_instance_types) > 0
    error_message = "Debe especificar al menos un tipo de instancia x86_64."
  }
}

variable "node_min_size" {
  description = "Cantidad mínima de nodos."
  type        = number
  default     = 2

  validation {
    condition     = var.node_min_size >= 1 && floor(var.node_min_size) == var.node_min_size
    error_message = "La cantidad mínima debe ser un entero positivo."
  }
}

variable "node_desired_size" {
  description = "Cantidad inicial deseada de nodos."
  type        = number
  default     = 3

  validation {
    condition     = floor(var.node_desired_size) == var.node_desired_size && var.node_desired_size >= var.node_min_size && var.node_desired_size <= var.node_max_size
    error_message = "La cantidad deseada debe ser entera y estar entre el mínimo y el máximo."
  }
}

variable "node_max_size" {
  description = "Cantidad máxima de nodos."
  type        = number
  default     = 6

  validation {
    condition     = floor(var.node_max_size) == var.node_max_size && var.node_max_size >= var.node_min_size
    error_message = "La cantidad máxima debe ser entera y no menor que la mínima."
  }
}

variable "node_disk_size" {
  description = "Tamaño del disco de cada nodo en GiB."
  type        = number
  default     = 40

  validation {
    condition     = var.node_disk_size >= 20 && floor(var.node_disk_size) == var.node_disk_size
    error_message = "El disco debe tener un tamaño entero de al menos 20 GiB."
  }
}

variable "db_instance_class" {
  description = "Clase de instancia RDS PostgreSQL."
  type        = string
  default     = "db.t4g.medium"
}

variable "db_allocated_storage" {
  description = "Almacenamiento inicial de PostgreSQL en GiB."
  type        = number
  default     = 20

  validation {
    condition     = var.db_allocated_storage >= 20 && floor(var.db_allocated_storage) == var.db_allocated_storage
    error_message = "El almacenamiento inicial debe ser un entero de al menos 20 GiB."
  }
}

variable "db_max_allocated_storage" {
  description = "Límite de escalado automático del almacenamiento en GiB."
  type        = number
  default     = 100

  validation {
    condition     = floor(var.db_max_allocated_storage) == var.db_max_allocated_storage && var.db_max_allocated_storage >= ceil(var.db_allocated_storage * 1.1)
    error_message = "El límite debe ser entero y superar el almacenamiento inicial en al menos un 10 %."
  }
}

variable "db_multi_az" {
  description = "Activa una instancia de reserva administrada por RDS en otra zona."
  type        = bool
  default     = true
}

variable "database_name" {
  description = "Nombre inicial de la base de datos PostgreSQL."
  type        = string
  default     = "vacaciones"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{0,62}$", var.database_name)) && !contains(["postgres", "template0", "template1"], var.database_name)
    error_message = "Use entre 1 y 63 caracteres alfanuméricos, comenzando con una letra, y evite nombres reservados."
  }
}

variable "tags" {
  description = "Etiquetas adicionales para los recursos AWS."
  type        = map(string)
  default     = {}
}