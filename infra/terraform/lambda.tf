resource "aws_iam_role" "lambda_role" {
  name = "${local.name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_app" {
  name = "${local.name}-lambda-app"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = [aws_sqs_queue.job_queue.arn, aws_sqs_queue.apply_queue.arn]
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

resource "aws_lambda_function" "scraper" {
  for_each      = toset(local.platforms)
  function_name = "${local.name}-scraper-${each.key}"
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.scraper.repository_url}:latest"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 900
  memory_size   = 1024
  environment {
    variables = {
      DEPLOY_TARGET = "aws"
      PLATFORM      = each.key
      JOB_QUEUE_URL = aws_sqs_queue.job_queue.url
      DATABASE_URL  = "postgresql://${var.db_username}:${data.aws_ssm_parameter.db_password.value}@${aws_db_instance.postgres.address}:5432/autoapply"
      S3_BUCKET     = aws_s3_bucket.storage.bucket
    }
  }
  image_config {
    command = ["infra.lambda_runtime.handler.scraper_handler"]
  }
  tags = local.tags
}

resource "aws_lambda_function" "matcher" {
  function_name = "${local.name}-matcher"
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.matcher.repository_url}:latest"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 900
  memory_size   = 2048
  environment {
    variables = {
      DEPLOY_TARGET     = "aws"
      APPLY_QUEUE_URL   = aws_sqs_queue.apply_queue.url
      DATABASE_URL      = "postgresql://${var.db_username}:${data.aws_ssm_parameter.db_password.value}@${aws_db_instance.postgres.address}:5432/autoapply"
      S3_BUCKET         = aws_s3_bucket.storage.bucket
      APPLIER_ANSWER_MODE = "local"
    }
  }
  image_config {
    command = ["infra.lambda_runtime.handler.matcher_handler"]
  }
  tags = local.tags
}

resource "aws_lambda_function" "report" {
  function_name = "${local.name}-report"
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.matcher.repository_url}:latest"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 900
  memory_size   = 1024
  environment {
    variables = {
      DEPLOY_TARGET = "aws"
      DATABASE_URL  = "postgresql://${var.db_username}:${data.aws_ssm_parameter.db_password.value}@${aws_db_instance.postgres.address}:5432/autoapply"
      S3_BUCKET     = aws_s3_bucket.storage.bucket
      SNS_TOPIC_ARN = aws_sns_topic.alerts.arn
    }
  }
  image_config {
    command = ["infra.lambda_runtime.handler.report_handler"]
  }
  tags = local.tags
}

resource "aws_lambda_event_source_mapping" "matcher_from_jobs" {
  event_source_arn = aws_sqs_queue.job_queue.arn
  function_name    = aws_lambda_function.matcher.arn
  batch_size       = 10
}

resource "aws_cloudwatch_event_target" "scraper" {
  for_each = toset(local.platforms)
  rule     = aws_cloudwatch_event_rule.scrape_schedule.name
  arn      = aws_lambda_function.scraper[each.key].arn
}

resource "aws_lambda_permission" "allow_eventbridge_scraper" {
  for_each      = toset(local.platforms)
  statement_id  = "AllowExecutionFromEventBridge-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scraper[each.key].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scrape_schedule.arn
}

resource "aws_cloudwatch_event_target" "report" {
  rule = aws_cloudwatch_event_rule.report_schedule.name
  arn  = aws_lambda_function.report.arn
}

resource "aws_lambda_permission" "allow_eventbridge_report" {
  statement_id  = "AllowExecutionFromEventBridgeReport"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.report.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.report_schedule.arn
}
