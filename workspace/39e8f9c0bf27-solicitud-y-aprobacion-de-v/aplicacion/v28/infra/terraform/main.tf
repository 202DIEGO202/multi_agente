terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.100.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7.0"
    }
  }
}

# Las credenciales se obtienen del entorno de ejecución.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Proyecto    = var.nombre
      Gestionado  = "Terraform"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.numero_zonas)
  private_subnets = [
    for index in range(var.numero_zonas) : cidrsubnet(var.vpc_cidr, 8, index)
  ]
  public_subnets = [
    for index in range(var.numero_zonas) : cidrsubnet(var.vpc_cidr, 8, index + 100)
  ]
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.21.0"

  name = var.nombre
  cidr = var.vpc_cidr
  azs  = local.azs

  public_subnets  = local.public_subnets
  private_subnets = local.private_subnets

  enable_dns_hostnames = true
  enable_dns_support   = true
  enable_nat_gateway   = true
  single_nat_gateway   = false
  one_nat_gateway_per_az = true

  # Etiquetas para el descubrimiento de subredes por balanceadores.
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.37.2"

  cluster_name    = var.nombre
  cluster_version = var.version_eks
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = false
  enable_irsa                     = true

  authentication_mode                      = "API_AND_CONFIG_MAP"
  enable_cluster_creator_admin_permissions = true

  cluster_enabled_log_types = [
    "api", "audit", "authenticator", "controllerManager", "scheduler"
  ]
  cloudwatch_log_group_retention_in_days = 30

  cluster_addons = {
    coredns = {}
    kube-proxy = {}
    vpc-cni = {
      before_compute = true
    }
  }

  eks_managed_node_groups = {
    aplicaciones = {
      name           = "${var.nombre}-aplicaciones"
      instance_types = var.tamanos_nodos.tipos_instancia
      ami_type       = "AL2023_x86_64_STANDARD"
      capacity_type  = "ON_DEMAND"
      min_size       = var.tamanos_nodos.minimo
      desired_size   = var.tamanos_nodos.deseado
      max_size       = var.tamanos_nodos.maximo
      disk_size      = var.tamanos_nodos.disco_gib
      subnet_ids     = module.vpc.private_subnets

      update_config = {
        max_unavailable = 1
      }

      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 2
      }
    }
  }
}

resource "aws_ecr_repository" "aplicaciones" {
  for_each = toset(["backend", "portal", "panel"])

  name                 = "${var.nombre}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "aplicaciones" {
  for_each   = aws_ecr_repository.aplicaciones
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Eliminar imágenes sin etiqueta después de 14 días"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}

resource "random_password" "postgres" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}:;,.?"
}

resource "aws_secretsmanager_secret" "postgres" {
  name_prefix             = "${var.nombre}-postgres-"
  description             = "Contraseña de PostgreSQL generada por Terraform"
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret_version" "postgres" {
  secret_id     = aws_secretsmanager_secret.postgres.id
  secret_string = random_password.postgres.result
}

resource "aws_db_subnet_group" "postgres" {
  name       = "${var.nombre}-postgres"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "postgres" {
  name_prefix = "${var.nombre}-postgres-"
  description = "Acceso PostgreSQL exclusivamente desde los nodos EKS"
  vpc_id      = module.vpc.vpc_id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres_desde_eks" {
  security_group_id            = aws_security_group.postgres.id
  referenced_security_group_id = module.eks.node_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL desde EKS"
}

resource "aws_db_parameter_group" "postgres" {
  name_prefix = "${var.nombre}-postgres-"
  family      = "postgres16"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "immediate"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "random_id" "snapshot" {
  byte_length = 4
}

resource "aws_db_instance" "postgres" {
  identifier        = "${var.nombre}-postgres"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.tamanos_rds.clase_instancia
  allocated_storage = var.tamanos_rds.almacenamiento_gib
  max_allocated_storage = var.tamanos_rds.almacenamiento_maximo_gib
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "vacaciones"
  username = "vacaciones_admin"
  password = random_password.postgres.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  parameter_group_name   = aws_db_parameter_group.postgres.name
  publicly_accessible    = false
  multi_az               = var.rds_multi_az

  backup_retention_period = 14
  backup_window           = "02:00-03:00"
  maintenance_window      = "sun:04:00-sun:05:00"
  auto_minor_version_upgrade = true
  allow_major_version_upgrade = false
  apply_immediately           = false
  copy_tags_to_snapshot        = true

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  deletion_protection             = true
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.nombre}-final-${random_id.snapshot.hex}"

  depends_on = [aws_secretsmanager_secret_version.postgres]
}