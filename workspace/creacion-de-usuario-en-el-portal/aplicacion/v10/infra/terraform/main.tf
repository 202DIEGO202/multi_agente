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

# Generar contraseña aleatoria para RDS
resource "random_password" "rds_password" {
  length           = 16
  special          = true
  override_characters = "@#%&*"
}

# Crear VPC con subredes públicas y privadas
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "3.18.2"

  name = var.nombre
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnets = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    Terraform   = "true"
    Environment = var.nombre
  }
}

# Crear secreto en Secrets Manager para la contraseña RDS
resource "aws_secretsmanager_secret" "rds_password_secret" {
  name = "${var.nombre}-rds-password"
  description = "Contraseña generada para la base de datos RDS PostgreSQL"
  tags = {
    Environment = var.nombre
  }
}

resource "aws_secretsmanager_secret_version" "rds_password_secret_version" {
  secret_id     = aws_secretsmanager_secret.rds_password_secret.id
  secret_string = jsonencode({
    password = random_password.rds_password.result
  })
}

# Crear clúster EKS
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "19.17.0"

  cluster_name    = var.nombre
  cluster_version = "1.27"
  subnets         = module.vpc.private_subnets
  vpc_id          = module.vpc.vpc_id

  node_groups = {
    main = {
      desired_capacity = var.eks_node_count
      max_capacity     = var.eks_node_count + 1
      min_capacity     = var.eks_node_count

      instance_type = var.eks_node_instance_type

      subnet_ids = module.vpc.private_subnets

      tags = {
        Name = "${var.nombre}-eks-node"
      }
    }
  }

  tags = {
    Environment = var.nombre
  }
}

# Repositorios ECR para backend, portal y panel
resource "aws_ecr_repository" "backend" {
  name = "${var.nombre}-backend"
  tags = {
    Environment = var.nombre
  }
}

resource "aws_ecr_repository" "portal" {
  name = "${var.nombre}-portal"
  tags = {
    Environment = var.nombre
  }
}

resource "aws_ecr_repository" "panel" {
  name = "${var.nombre}-panel"
  tags = {
    Environment = var.nombre
  }
}

# RDS PostgreSQL en subred privada
resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "${var.nombre}-rds-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name        = "${var.nombre} RDS subnet group"
    Environment = var.nombre
  }
}

resource "aws_db_instance" "postgresql" {
  identifier              = "${var.nombre}-postgresql"
  engine                  = "postgres"
  engine_version          = "16.0"
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
  backup_retention_period = 7
  deletion_protection     = false
  tags = {
    Environment = var.nombre
  }
}