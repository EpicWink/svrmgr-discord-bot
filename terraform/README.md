# Server manager infrastructure Terraform configuration

Creates infrastructure needed to start/stop EC2 instances and update Discord messages,
including a serverless function and necessary IAM identities and permissions.

You should only ever have to deploy this once.

## Usage

### Setup

1. Create file `dev.s3.tfbackend` (`dev` can be replace with anything), for example:

   ```hcl
   region         = "ap-southeast-2"
   bucket         = "my-bucket"
   key            = "terraform-states/svrmgr-dev.tfstate"
   dynamodb_table = "terraform-state-locks"
   ```

2. Initialise Terraform:

   ```shell
   terraform init -backend-config dev.s3.tfbackend
   ```

### Deploy

1. Create deployment package:

   ```shell
   python ../scripts/build.py
   ```

2. Apply Terraform configuration:

   ```shell
   terraform apply
   ```

   See [variables.tf](./variables.tf) for required and optional input variables.
