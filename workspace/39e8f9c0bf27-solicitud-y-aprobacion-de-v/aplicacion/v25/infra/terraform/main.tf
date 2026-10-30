terraform {
  required_version = ">= 1.5.7, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.100.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7.2"
    }
  }
}

# Las credenciales se obtienen del entorno o del rol de ejecución.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.nombre
      ManagedBy = "Terraform"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs           = slice(data.aws_availability_zones.available.names, 0, var.numero_az)
  db_identifier = "${var.nombre}-postgres"
  repositories = toset(["backend", "portal", "panel"])
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.21.0"

  name = "${var.nombre}-vpc"
  cidr = var.vpc_cidr
  azs  = local.azs

  public_subnets   = [for index, az in local.azs : cidrsubnet(var.vpc_cidr, 8, index)]
  private_subnets  = [for index, az in local.azs : cidrsubnet(var.vpc_cidr, 8, index + 10)]
  database_subnets = [for index, az in local.azs : cidrsubnet(var.vpc_cidr, 8, index + 20)]

  enable_dns_support   = true
  enable_dns_hostnames = true

  enable_nat_gateway     = true
  single_nat_gateway     = var.nat_gateway_unico
  one_nat_gateway_per_az = !var.nat_gateway_unico

  map_public_ip_on_launch           = false
  create_database_subnet_group      = true
  create_database_subnet_route_table = true
  create_database_nat_gateway_route = false
  create_database_internet_gateway_route = false

  # Etiquetas para el descubrimiento de subredes por balanceadores de Kubernetes.
  public_subnet_tags = {
    "kubernetes.io/role/elb"                      = "1"
    "kubernetes.io/cluster/${var.nombre}"         = "shared"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"              = "1"
    "kubernetes.io/cluster/${var.nombre}"          = "shared"
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.31.6"

  cluster_name    = var.nombre
  cluster_version = var.version_kubernetes

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # El API de Kubernetes solo es accesible desde la VPC.
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = false

  authentication_mode                      = "API_AND_CONFIG_MAP"
  enable_cluster_creator_admin_permissions = true

  cluster_enabled_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]
  cloudwatch_log_group_retention_in_days = var.retencion_logs_dias

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent    = true
      before_compute = true
    }
  }

  enable_irsa = true

  eks_managed_node_groups = {
    aplicaciones = {
      name           = "${var.nombre}-apps"
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.tipos_instancia_nodos
      capacity_type  = "ON_DEMAND"
      disk_size      = var.disco_nodos_gib

      min_size     = var.tamano_node_group.minimo
      max_size     = var.tamano_node_group.maximo
      desired_size = var.tamano_node_group.deseado

      subnet_ids = module.vpc.private_subnets

      update_config = {
        max_unavailable = 1
      }

      labels = {
        workload = "aplicaciones"
      }
    }
  }
}

resource "aws_ecr_repository" "applications" {
  for_each = local.repositories

  name                 = "${var.nombre}/${each.value}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "applications" {
  for_each   = aws_ecr_repository.applications
  repository = each.value.name

  # Solo se eliminan imágenes sin etiqueta.
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Eliminar imagenes sin etiqueta tras 14 dias"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = {
        type = "expire"
      }
    }]
  })
}

resource "aws_security_group" "postgres" {
  name_prefix = "${var.nombre}-postgres-"
  description = "Acceso PostgreSQL desde los nodos EKS"
  vpc_id      = module.vpc.vpc_id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_eks" {
  security_group_id            = aws_security_group.postgres.id
  referenced_security_group_id = module.eks.node_security_group_id
  description                 = "PostgreSQL desde las aplicaciones en EKS"
  ip_protocol                 = "tcp"
  from_port                   = 5432
  to_port                     = 5432
}

resource "aws_db_parameter_group" "postgres" {
  name_prefix = "${var.nombre}-postgres16-"
  family      = "postgres16"
  description = "PostgreSQL 16 con conexiones TLS obligatorias"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# La contraseña se genera sin introducir credenciales en los archivos.
resource "random_password" "postgres" {
  length  = 32
  special = false
}

resource "random_id" "snapshot" {
  byte_length = 4
}

resource "aws_cloudwatch_log_group" "postgres" {
  for_each = toset(["postgresql", "upgrade"])

  name              = "/aws/rds/instance/${local.db_identifier}/${each.value}"
  retention_in_days = var.retencion_logs_dias
}

resource "aws_db_instance" "postgres" {
  identifier = local.db_identifier

  engine               = "postgres"
  engine_version       = var.version_postgresql
  instance_class       = var.clase_instancia_rds
  parameter_group_name = aws_db_parameter_group.postgres.name

  db_name  = var.nombre_base_datos
  username = var.usuario_base_datos
  password = random_password.postgres.result
  port     = 5432

  allocated_storage     = var.almacenamiento_rds.inicial_gib
  max_allocated_storage = var.almacenamiento_rds.maximo_gib
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  publicly_accessible    = false
  multi_az               = var.rds_multi_az

  backup_retention_period = var.retencion_backup_dias
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:05:00-sun:06:00"
  copy_tags_to_snapshot    = true

  auto_minor_version_upgrade = true
  allow_major_version_upgrade = false
  apply_immediately           = false
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  deletion_protection       = var.proteccion_eliminacion_rds
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.db_identifier}-final-${random_id.snapshot.hex}"

  depends_on = [aws_cloudwatch_log_group.postgres]
}

resource "aws_secretsmanager_secret" "postgres" {
  name                    = "${var.nombre}/rds/postgres"
  description             = "Credenciales de PostgreSQL para la aplicacion"
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret_version" "postgres" {
  secret_id = aws_secretsmanager_secret.postgres.id

  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.postgres.address
    port     = aws_db_instance.postgres.port
    dbname   = aws_db_instance.postgres.db_name
    username = aws_db_instance.postgres.username
    password = random_password.postgres.result
  })
}