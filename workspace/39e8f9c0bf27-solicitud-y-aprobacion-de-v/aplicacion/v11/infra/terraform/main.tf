terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.83"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# Las credenciales se obtienen del entorno de ejecución.
provider "aws" {
  region = var.region

  default_tags {
    tags = merge(var.tags, {
      Project   = var.name
      ManagedBy = "Terraform"
    })
  }
}

data "aws_availability_zones" "available" {
  state = "available"

  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)

  public_subnets   = [for i in range(var.availability_zone_count) : cidrsubnet(var.vpc_cidr, 4, i)]
  private_subnets  = [for i in range(var.availability_zone_count) : cidrsubnet(var.vpc_cidr, 4, i + var.availability_zone_count)]
  database_subnets = [for i in range(var.availability_zone_count) : cidrsubnet(var.vpc_cidr, 4, i + 2 * var.availability_zone_count)]
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.21.0"

  name = var.name
  cidr = var.vpc_cidr
  azs  = local.azs

  public_subnets   = local.public_subnets
  private_subnets  = local.private_subnets
  database_subnets = local.database_subnets

  enable_dns_support   = true
  enable_dns_hostnames = true

  # Una salida NAT por zona para los nodos privados.
  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true

  create_database_subnet_group           = true
  create_database_subnet_route_table     = true
  create_database_nat_gateway_route      = false
  create_database_internet_gateway_route = false

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.31.0"

  cluster_name    = var.name
  cluster_version = var.kubernetes_version

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.private_subnets

  # La API de Kubernetes solo es accesible desde la red privada.
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = false

  authentication_mode                      = "API"
  enable_cluster_creator_admin_permissions = true
  enable_irsa                              = true

  cluster_enabled_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
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
    applications = {
      name           = "${var.name}-apps"
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.node_instance_types
      capacity_type  = "ON_DEMAND"

      min_size     = var.node_min_size
      desired_size = var.node_desired_size
      max_size     = var.node_max_size
      disk_size    = var.node_disk_size

      subnet_ids = module.vpc.private_subnets

      update_config = {
        max_unavailable = 1
      }

      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 1
      }

      labels = {
        workload = "applications"
      }
    }
  }
}

resource "aws_ecr_repository" "applications" {
  for_each = toset(["backend", "portal", "panel"])

  name                 = "${var.name}/${each.key}"
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
  for_each = aws_ecr_repository.applications

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
      action = {
        type = "expire"
      }
    }]
  })
}

resource "aws_security_group" "database" {
  name_prefix = "${var.name}-database-"
  description = "Acceso PostgreSQL desde los nodos EKS"
  vpc_id      = module.vpc.vpc_id

  # Sin salida general ni acceso público a la base de datos.
  tags = {
    Name = "${var.name}-database"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "database_from_nodes" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = module.eks.node_security_group_id
  description                  = "PostgreSQL desde los nodos de aplicaciones"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "random_password" "database" {
  length           = 32
  special          = true
  override_special = "_%+=-"
  min_lower        = 2
  min_upper        = 2
  min_numeric      = 2
  min_special      = 2
}

resource "aws_secretsmanager_secret" "database" {
  name                    = "${var.name}/rds/credentials"
  description             = "Credenciales administrativas de PostgreSQL"
  recovery_window_in_days = 30
}

resource "aws_db_parameter_group" "database" {
  name_prefix = "${var.name}-postgres16-"
  family      = "postgres16"
  description = "PostgreSQL 16 con conexiones TLS obligatorias"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "immediate"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "database" {
  identifier = "${var.name}-db"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.database_name
  username = "db_admin"
  password = random_password.database.result
  port     = 5432

  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.database.id]
  parameter_group_name   = aws_db_parameter_group.database.name
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:05:00-sun:06:00"

  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  apply_immediately           = false

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  copy_tags_to_snapshot           = true
  deletion_protection            = true
  skip_final_snapshot            = false
  final_snapshot_identifier      = "${var.name}-final"

  depends_on = [aws_vpc_security_group_ingress_rule.database_from_nodes]
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id

  # La contraseña se genera al aplicar y nunca se publica como output.
  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.database.address
    port     = aws_db_instance.database.port
    dbname   = aws_db_instance.database.db_name
    username = aws_db_instance.database.username
    password = random_password.database.result
  })
}