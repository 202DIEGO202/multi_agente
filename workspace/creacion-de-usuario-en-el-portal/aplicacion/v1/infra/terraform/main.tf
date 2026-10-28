terraform {
  required_version = ">= 1.1"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# VPC con subredes públicas y privadas
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "3.18.2"

  name = var.project_name
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnets = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    "Project" = var.project_name
  }
}

# Cluster EKS
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "18.29.0"

  cluster_name    = var.project_name
  cluster_version = "1.27"
  subnets        = module.vpc.private_subnets
  vpc_id         = module.vpc.vpc_id

  node_groups = {
    main = {
      desired_capacity = var.eks_node_desired_capacity
      max_capacity     = var.eks_node_max_capacity
      min_capacity     = var.eks_node_min_capacity

      instance_type = var.eks_node_instance_type

      subnet_ids = module.vpc.private_subnets

      tags = {
        "Project" = var.project_name
      }
    }
  }

  tags = {
    "Project" = var.project_name
  }
}

# Repositorios ECR para backend y frontend
resource "aws_ecr_repository" "backend" {
  name = "${var.project_name}-backend"
  tags = {
    Project = var.project_name
  }
}

resource "aws_ecr_repository" "frontend" {
  name = "${var.project_name}-frontend"
  tags = {
    Project = var.project_name
  }
}

# Secreto para contraseña RDS
resource "random_password" "rds_password" {
  length  = 16
  special = true
}

resource "aws_secretsmanager_secret" "rds_password_secret" {
  name = "${var.project_name}-rds-password"
  tags = {
    Project = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "rds_password_secret_version" {
  secret_id     = aws_secretsmanager_secret.rds_password_secret.id
  secret_string = jsonencode({
    password = random_password.rds_password.result
  })
}

# RDS PostgreSQL en subred privada
resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "${var.project_name}-rds-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Project = var.project_name
  }
}

resource "aws_db_instance" "postgres" {
  identifier              = "${var.project_name}-postgres"
  engine                  = "postgres"
  engine_version          = "15.3"
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage
  storage_type            = "gp3"
  db_subnet_group_name    = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids  = [module.vpc.default_security_group_id]
  multi_az                = false
  publicly_accessible     = false
  username                = "admin"
  password                = random_password.rds_password.result
  skip_final_snapshot     = true
  deletion_protection     = false
  backup_retention_period = 7
  tags = {
    Project = var.project_name
  }
}

# Outputs
output "eks_cluster_endpoint" {
  description = "Endpoint del clúster EKS"
  value       = module.eks.cluster_endpoint
}

output "ecr_backend_url" {
  description = "URL del repositorio ECR backend"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  description = "URL del repositorio ECR frontend"
  value       = aws_ecr_repository.frontend.repository_url
}

output "rds_endpoint" {
  description = "Endpoint de la base de datos RDS PostgreSQL"
  value       = aws_db_instance.postgres.endpoint
}

# Data source para AZs
data "aws_availability_zones" "available" {}