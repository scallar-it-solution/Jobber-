terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name      = "${var.project_name}-${var.environment}"
  platforms = ["linkedin", "indeed", "naukri", "wellfound"]
  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

data "aws_ssm_parameter" "db_password" {
  name            = var.db_password_ssm_parameter
  with_decryption = true
}

resource "aws_vpc" "main" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(local.tags, { Name = "${local.name}-vpc" })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.tags, { Name = "${local.name}-igw" })
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "${local.name}-public-${count.index + 1}" })
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = merge(local.tags, { Name = "${local.name}-public-rt" })
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "Allow database traffic from app security group"
  vpc_id      = aws_vpc.main.id
  tags        = local.tags
}

resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "AutoApply application tasks"
  vpc_id      = aws_vpc.main.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_security_group_rule" "app_to_rds" {
  type                     = "ingress"
  security_group_id        = aws_security_group.rds.id
  source_security_group_id = aws_security_group.app.id
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db-subnets"
  subnet_ids = aws_subnet.public[*].id
  tags       = local.tags
}

resource "aws_db_instance" "postgres" {
  identifier             = "${local.name}-postgres"
  engine                 = "postgres"
  engine_version         = "16.3"
  instance_class         = "db.t4g.micro"
  allocated_storage      = 20
  db_name                = "autoapply"
  username               = var.db_username
  password               = data.aws_ssm_parameter.db_password.value
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  skip_final_snapshot    = true
  deletion_protection    = false
  tags                   = local.tags
}

resource "aws_s3_bucket" "storage" {
  bucket = var.s3_bucket_name
  tags   = local.tags
}

resource "aws_s3_bucket_server_side_encryption_configuration" "storage" {
  bucket = aws_s3_bucket.storage.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_sqs_queue" "job_queue" {
  name                       = "${local.name}-job-queue"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 1209600
  tags                       = local.tags
}

resource "aws_sqs_queue" "apply_queue" {
  name                       = "${local.name}-apply-queue"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 1209600
  tags                       = local.tags
}

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
  tags = local.tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.sns_alert_email
}

resource "aws_ecr_repository" "scraper" {
  name                 = "${local.name}-scraper"
  image_tag_mutability = "MUTABLE"
  tags                 = local.tags
}

resource "aws_ecr_repository" "matcher" {
  name                 = "${local.name}-matcher"
  image_tag_mutability = "MUTABLE"
  tags                 = local.tags
}

resource "aws_ecr_repository" "applier" {
  name                 = "${local.name}-applier"
  image_tag_mutability = "MUTABLE"
  tags                 = local.tags
}

resource "aws_cloudwatch_event_rule" "scrape_schedule" {
  name                = "${local.name}-scrape"
  description         = "Run scrapers at 07:00 and 18:00 IST"
  schedule_expression = "cron(30 1,12 * * ? *)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_rule" "report_schedule" {
  name                = "${local.name}-daily-report"
  description         = "Generate daily report at 19:00 IST"
  schedule_expression = "cron(30 13 * * ? *)"
  tags                = local.tags
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.address
}

output "s3_bucket" {
  value = aws_s3_bucket.storage.bucket
}

output "job_queue_url" {
  value = aws_sqs_queue.job_queue.url
}

output "apply_queue_url" {
  value = aws_sqs_queue.apply_queue.url
}
