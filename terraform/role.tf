# Function IAM role

data "aws_iam_policy_document" "svrmgr_assume_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "svrmgr" {
  assume_role_policy = data.aws_iam_policy_document.svrmgr_assume_role_policy.json
  description        = "svrmgr Lambda function execution role"
  name               = "svrmgr-${var.environment_name}"
}

data "aws_iam_policy_document" "svrmgr_manage_ec2" {
  statement {
    actions = [
      "ec2:DescribeTags",
      "ec2:DescribeInstanceStatus",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      values   = [var.aws_region]
      variable = "ec2:Region"
    }
  }

  statement {
    actions = [
      "ec2:StartInstances",
      "ec2:StopInstances",
    ]
    resources = ["arn:aws:ec2:${var.aws_region}:*:instance/*"]

    condition {
      test     = "StringEquals"
      values   = [var.environment_name]
      variable = "aws:ResourceTag/env"
    }
  }
}

resource "aws_iam_role_policy" "svrmgr_manage_ec2" {
  name   = "svrmgr-ec2-manage-${var.environment_name}"
  policy = data.aws_iam_policy_document.svrmgr_manage_ec2.json
  role   = aws_iam_role.svrmgr.id
}

resource "aws_iam_role_policy_attachment" "svrmgr_send_logs" {
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLambdaInsightsExecutionRolePolicy"
  role       = aws_iam_role.svrmgr.id
}

resource "aws_iam_role_policy_attachment" "svrmgr_send_insights_logs" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.svrmgr.id
}
