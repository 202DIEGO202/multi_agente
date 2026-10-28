terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "aws" {
  region = var.region
}

# Generar contraseña para RDS en Secrets Manager
resource "random_password" "rds_password" {
  length  = 16
  special = true
  override_characters = "@#%&*"
}

resource "aws_secretsmanager_secret" "rds_password_secret" {
  name = "${var.name}-rds-password"
}

resource "aws_secretsmanager_secret_version" "rds_password_secret_version" {
  secret_id     = aws_secretsmanager_secret.rds_password_secret.id
  secret_string = jsonencode({
    username = var.rds_username
    password = random_password.rds_password.result
  })
}

# Crear VPC con subredes públicas y privadas
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "3.18.2"

  name = var.name
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  public_subnets  = var.public_subnets
  private_subnets = var.private_subnets

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    Terraform   = "true"
    Environment = var.name
  }
}

# Crear cluster EKS
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "19.17.0"

  cluster_name    = var.name
  cluster_version = var.eks_version
  subnets         = module.vpc.private_subnets
  vpc_id          = module.vpc.vpc_id

  node_groups = {
    main = {
      desired_capacity = var.node_group_desired_capacity
      max_capacity     = var.node_group_max_capacity
      min_capacity     = var.node_group_min_capacity

      instance_types = var.node_group_instance_types

      disk_size = 20

      tags = {
        Name = "${var.name}-eks-node"
      }
    }
  }

  tags = {
    Environment = var.name
    Terraform   = "true"
  }
}

# Crear repositorios ECR para backend, portal y panel
resource "aws_ecr_repository" "backend" {
  name = "${var.name}-backend"
  image_tag_mutability = "MUTABLE"
  tags = {
    Environment = var.name
  }
}

resource "aws_ecr_repository" "portal" {
  name = "${var.name}-portal"
  image_tag_mutability = "MUTABLE"
  tags = {
    Environment = var.name
  }
}

resource "aws_ecr_repository" "panel" {
  name = "${var.name}-panel"
  image_tag_mutability = "MUTABLE"
  tags = {
    Environment = var.name
  }
}

# Crear RDS PostgreSQL en subred privada
resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "${var.name}-rds-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name = "${var.name}-rds-subnet-group"
  }
}

resource "aws_db_instance" "postgresql" {
  identifier              = "${var.name}-postgresql"
  engine                  = "postgres"
  engine_version          = var.rds_engine_version
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage
  storage_type            = "gp3"
  db_subnet_group_name    = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids  = [module.vpc.default_security_group_id]
  multi_az                = false
  publicly_accessible     = false
  skip_final_snapshot     = true
  username                = var.rds_username
  password                = random_password.rds_password.result
  deletion_protection     = false
  backup_retention_period = 7
  tags = {
    Environment = var.name
  }
}

# Salida de datos
output "eks_cluster_endpoint" {
  description = "Endpoint del clúster EKS"
  value       = module.eks.cluster_endpoint
}

output "ecr_backend_url" {
  description = "URL del repositorio ECR backend"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_portal_url" {
  description = "URL del repositorio ECR portal"
  value       = aws_ecr_repository.portal.repository_url
}

output "ecr_panel_url" {
  description = "URL del repositorio ECR panel"
  value       = aws_ecr_repository.panel.repository_url
}

output "rds_endpoint" {
  description = "Endpoint de la base de datos RDS PostgreSQL"
  value       = aws_db_instance.postgresql.endpoint
}

output "rds_secret_arn" {
  description = "ARN del secreto en Secrets Manager para la contraseña RDS"
  value       = aws_secretsmanager_secret.rds_password_secret.arn
}

# Data source para zonas de disponibilidad
data "aws_availability_zones" "available" {}