# Lambda function

locals {
  deployment_package_path = "${path.module}/../build/dist.zip"
}

resource "aws_lambda_function" "svrmgr" {
  architectures    = ["x86_64"]
  description      = "Manage EC2 instances as a Discord bot"
  function_name    = "svrmgr-${var.environment_name}"
  filename         = local.deployment_package_path
  handler          = "main.main"
  memory_size      = 128
  package_type     = "Zip"
  role             = aws_iam_role.svrmgr.arn
  runtime          = "python3.12"
  source_code_hash = filebase64sha256(local.deployment_package_path)

  environment {
    variables = {
      SVRMGR_DISCORD_APP_PUBLIC_KEY = var.discord_public_key
    }
  }

  logging_config {
    log_format = "JSON"
  }
}

resource "aws_lambda_function_url" "svrmgr" {
  authorization_type = "NONE"
  function_name      = aws_lambda_function.svrmgr.function_name
  invoke_mode        = "BUFFERED"
}
