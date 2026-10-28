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
  override_characters = "@#$%&*"
}

resource "aws_secretsmanager_secret" "rds_password_secret" {
  name = "${var.name}-rds-password"
}

resource "aws_secretsmanager_secret_version" "rds_password_secret_version" {
  secret_id     = aws_secretsmanager_secret.rds_password_secret.id
  secret_string = random_password.rds_password.result
}

# Crear VPC con subredes públicas y privadas
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "3.18.2"

  name = var.name
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnets = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    Terraform   = "true"
    Environment = var.name
  }
}

# Crear clúster EKS
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "18.29.0"

  cluster_name    = var.name
  cluster_version = "1.27"
  subnets        = module.vpc.private_subnets
  vpc_id         = module.vpc.vpc_id

  node_groups = {
    default = {
      desired_capacity = var.eks_node_desired_capacity
      max_capacity     = var.eks_node_max_capacity
      min_capacity     = var.eks_node_min_capacity

      instance_type = var.eks_node_instance_type

      key_name = var.key_name

      subnet_ids = module.vpc.private_subnets

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

# Repositorios ECR para backend, portal y panel
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

# RDS PostgreSQL en subred privada
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
  engine_version          = "16.0"
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage
  storage_type            = "gp3"
  db_subnet_group_name    = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids  = [module.vpc.default_security_group_id]
  multi_az                = false
  publicly_accessible     = false
  username                = var.rds_username
  password                = random_password.rds_password.result
  skip_final_snapshot     = true
  deletion_protection     = false
  backup_retention_period = 7
  tags = {
    Environment = var.name
  }
}