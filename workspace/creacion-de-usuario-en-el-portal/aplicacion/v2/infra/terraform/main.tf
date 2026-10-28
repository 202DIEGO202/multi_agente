terraform {
  required_version = ">= 1.1"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.region
}

// Generar contraseña aleatoria para RDS
resource "random_password" "rds_password" {
  length  = 16
  special = true
}

// VPC con subredes públicas y privadas
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "3.18.2"

  name = var.project_name
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnets = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    "Project" = var.project_name
  }
}

data "aws_availability_zones" "available" {}

// EKS Cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "18.29.0"

  cluster_name    = var.project_name
  cluster_version = "1.27"
  subnets        = module.vpc.private_subnets
  vpc_id         = module.vpc.vpc_id

  node_groups = {
    default = {
      desired_capacity = var.eks_node_desired_capacity
      max_capacity     = var.eks_node_max_capacity
      min_capacity     = var.eks_node_min_capacity

      instance_type = var.eks_node_instance_type

      subnet_ids = module.vpc.private_subnets

      tags = {
        "Name"    = "${var.project_name}-eks-node"
        "Project" = var.project_name
      }
    }
  }

  tags = {
    "Project" = var.project_name
  }
}

// Repositorios ECR para backend y frontend
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

// Secrets Manager para contraseña RDS
resource "aws_secretsmanager_secret" "rds_password" {
  name = "${var.project_name}-rds-password"
  description = "Contraseña generada para RDS PostgreSQL"
  tags = {
    Project = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "rds_password_version" {
  secret_id     = aws_secretsmanager_secret.rds_password.id
  secret_string = jsonencode({
    password = random_password.rds_password.result
  })
}

// RDS PostgreSQL en subred privada
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
  skip_final_snapshot     = true
  username                = "admin"
  password                = random_password.rds_password.result
  deletion_protection     = false
  backup_retention_period = 7
  tags = {
    Project = var.project_name
  }
}

// Nota: Integración con Microsoft Active Directory y SMTP no incluida en Terraform
// Monitoreo con CloudWatch se asume habilitado por defecto en AWS