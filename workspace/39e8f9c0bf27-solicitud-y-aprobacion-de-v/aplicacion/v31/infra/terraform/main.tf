terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.100"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# Las credenciales se obtienen del entorno o del rol de ejecución.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Proyecto   = var.nombre
      Gestionado = "Terraform"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"

  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required", "opted-in"]
  }
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.numero_az)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.19.0"

  name = var.nombre
  cidr = "10.0.0.0/16"
  azs  = local.azs

  public_subnets   = [for i in range(var.numero_az) : cidrsubnet("10.0.0.0/16", 8, i)]
  private_subnets  = [for i in range(var.numero_az) : cidrsubnet("10.0.0.0/16", 8, i + 16)]
  database_subnets = [for i in range(var.numero_az) : cidrsubnet("10.0.0.0/16", 8, i + 32)]

  enable_dns_support   = true
  enable_dns_hostnames = true

  # Un NAT por zona evita depender de una única zona para la salida.
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
  version = "20.31.6"

  cluster_name    = var.nombre
  cluster_version = var.version_eks

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # El API de Kubernetes solo es accesible desde la red privada.
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = false

  enable_cluster_creator_admin_permissions = true
  enable_irsa                              = true

  cluster_enabled_log_types              = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  cloudwatch_log_group_retention_in_days  = var.retencion_logs_dias
  cloudwatch_log_group_class              = "STANDARD"
  enable_kms_key_rotation                 = true

  cluster_addons = {
    coredns = {}
    kube-proxy = {}
    vpc-cni = {
      before_compute = true
    }
  }

  eks_managed_node_groups = {
    aplicaciones = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.tipos_instancia_nodos
      capacity_type  = "ON_DEMAND"

      min_size     = var.nodos_minimos
      desired_size = var.nodos_deseados
      max_size     = var.nodos_maximos

      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = var.disco_nodos_gb
            volume_type           = "gp3"
            encrypted             = true
            delete_on_termination = true
          }
        }
      }

      update_config = {
        max_unavailable = 1
      }

      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 1
      }

      labels = {
        carga = "aplicaciones"
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
      description  = "Eliminar imágenes sin etiqueta tras 14 días"
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
  description = "PostgreSQL privado para los nodos EKS"
  vpc_id      = module.vpc.vpc_id

  # Sin salida iniciada por RDS; las respuestas son stateful.
  tags = {
    Name = "${var.nombre}-postgres"
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres_desde_eks" {
  security_group_id            = aws_security_group.postgres.id
  referenced_security_group_id = module.eks.node_security_group_id
  description                  = "PostgreSQL desde nodos EKS"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "random_password" "postgres" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}:?"
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  min_special      = 2
}

resource "random_id" "snapshot" {
  byte_length = 4
}

resource "aws_db_parameter_group" "postgres" {
  name_prefix = "${var.nombre}-postgres16-"
  family      = "postgres16"
  description = "PostgreSQL 16 con TLS obligatorio"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "postgres" {
  identifier = "${var.nombre}-postgres"

  engine               = "postgres"
  engine_version       = "16"
  instance_class       = var.clase_instancia_rds
  db_name              = "vacaciones"
  username             = "app_admin"
  password             = random_password.postgres.result
  port                 = 5432
  parameter_group_name = aws_db_parameter_group.postgres.name

  allocated_storage     = var.almacenamiento_rds_gb
  max_allocated_storage = var.almacenamiento_rds_max_gb
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  publicly_accessible    = false
  multi_az               = var.rds_multi_az

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:05:00-sun:06:00"
  copy_tags_to_snapshot    = true

  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  apply_immediately           = false
  deletion_protection         = var.proteccion_borrado_rds
  skip_final_snapshot         = false
  final_snapshot_identifier   = "${var.nombre}-final-${random_id.snapshot.hex}"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  lifecycle {
    precondition {
      condition     = var.almacenamiento_rds_max_gb >= ceil(var.almacenamiento_rds_gb * 1.1)
      error_message = "El máximo de almacenamiento RDS debe superar al inicial al menos un 10 %."
    }
  }
}

resource "aws_secretsmanager_secret" "postgres" {
  name_prefix             = "${var.nombre}/postgres-"
  description             = "Conexión privada a PostgreSQL"
  recovery_window_in_days = 30
}

# La contraseña se genera, no se incorpora al código ni a los outputs.
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