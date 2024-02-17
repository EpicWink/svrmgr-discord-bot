# Terraform outputs

output "function_url" {
  description = "Function invocation URL"
  value       = aws_lambda_function_url.svrmgr.function_url
}
