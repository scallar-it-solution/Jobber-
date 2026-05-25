variable "project_name" {
  description = "Name prefix for AWS resources."
  type        = string
  default     = "autoapply"
}

variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "prod"
}

variable "db_username" {
  description = "RDS PostgreSQL username."
  type        = string
  default     = "autoapply"
}

variable "db_password_ssm_parameter" {
  description = "SSM SecureString parameter containing the RDS password."
  type        = string
  default     = "/autoapply/prod/db_password"
}

variable "sns_alert_email" {
  description = "Email for daily summaries and alerts."
  type        = string
  default     = ""
}

variable "s3_bucket_name" {
  description = "S3 bucket for resumes and reports."
  type        = string
  default     = "autoapply-deepesh"
}

variable "applier_desired_count" {
  description = "Fargate applier desired task count. Keep 0 for lowest cost, raise to 1 for always-on."
  type        = number
  default     = 0
}
