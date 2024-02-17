# Server manager development

Install [Python](https://www.python.org/).

Install dependencies:

```shell
pip install -r app.requirements.txt -r dev.requirements.txt
```

## Testing

Install test dependencies:

```shell
pip install -r tests/requirements.txt
```

Run tests:

```shell
pytest
```

## Formatting

Format Python code:

```shell
black .
isort .
```

Format Terraform code:

```shell
cd terraform
terraform fmt
```

## Update dependency pins

Run pip-tools compile:

```shell
pip-compile
```

Should be run with the same version of Python as the Lambda function's runtime
(currently 3.12), eg `python3.12 -m piptools compile`.

Then remove Lambda runtime-provided packages from
[app.requirements.txt](./app.requirements.txt): `urllib3`, `six`, `jmespath`,
`python-dateutil`, `botocore`, `s3transfer`, `boto3`.
