resource "aws_ecs_cluster" "main" {
  name = "${local.name}-cluster"
  tags = local.tags
}

resource "aws_cloudwatch_log_group" "applier" {
  name              = "/ecs/${local.name}-applier"
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_iam_role" "ecs_execution_role" {
  name = "${local.name}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "${local.name}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "ecs_task_app" {
  name = "${local.name}-ecs-task-app"
  role = aws_iam_role.ecs_task_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.apply_queue.arn
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject"]
        Resource = ["${aws_s3_bucket.storage.arn}/*"]
      },
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter"]
        Resource = [data.aws_ssm_parameter.db_password.arn]
      }
    ]
  })
}

resource "aws_ecs_task_definition" "applier" {
  family                   = "${local.name}-applier"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "applier"
      image     = "${aws_ecr_repository.applier.repository_url}:latest"
      essential = true
      environment = [
        { name = "DEPLOY_TARGET", value = "aws" },
        { name = "APPLY_QUEUE_URL", value = aws_sqs_queue.apply_queue.url },
        { name = "DATABASE_URL", value = "postgresql://${var.db_username}:${data.aws_ssm_parameter.db_password.value}@${aws_db_instance.postgres.address}:5432/autoapply" },
        { name = "S3_BUCKET", value = aws_s3_bucket.storage.bucket },
        { name = "APPLIER_ANSWER_MODE", value = "local" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.applier.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_service" "applier" {
  name            = "${local.name}-applier"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.applier.arn
  desired_count   = var.applier_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  tags = local.tags
}
