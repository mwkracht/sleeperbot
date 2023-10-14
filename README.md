# SleeperBot

My feeble attempt at automating management for a Sleeper dynasty football league.

## Development Mode

`docker-compose run --rm develop`

## Committing

Run the following command in base repository directory to install pre-commit hooks before first commit:

`pre-commit install`


## Deployment

Deployment builds a docker image, publishes it to an AWS ECR repository, and then updates an AWS Lambda function to consume this new image. The deployment process is found in `deploy.sh` and follows [this guide](aws-python-lambda) from AWS.

Deployment expects three variables to be present:

- `SLEEPERBOT_AWS_ACCOUNT` - Account ID for the AWS account used to manage AWS deployment resources
- `SLEEPERBOT_REPO` - AWS ECR Repository URL to upload docker images (ex. `<account_id>.dkr.ecr.us-east-1.amazonaws.com/<repo_name>`)
- `SLEEPERBOT_FUNCTION` - AWS Lambda function name that is running the published docker image


[aws-python-lambda]: https://docs.aws.amazon.com/lambda/latest/dg/python-image.html
