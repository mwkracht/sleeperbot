#!/bin/sh

# do not keep more than the latest image so we don't exceed free tier usage
aws ecr batch-delete-image \
    --repository-name sleeperbot \
    --image-ids "$(aws ecr list-images --repository-name sleeperbot --query 'imageIds[*]' --output json
)" || true

aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $SLEEPERBOT_AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

docker build --platform linux/amd64 --target build -t sleeperbot:latest .

docker tag sleeperbot:latest $SLEEPERBOT_REPO:latest
docker push $SLEEPERBOT_REPO:latest

aws lambda update-function-code --function-name $SLEEPERBOT_FUNCTION --image-uri $SLEEPERBOT_REPO:latest
