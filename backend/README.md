# Backend Subsystem

Serverless event-driven architecture using AWS SAM:
- `template.yaml`: CloudFormation / SAM infrastructure defining S3, SQS, DynamoDB, API Gateway, and Lambda.
- `common_layer/`: Reusable response formatters and utility modules.
- `handlers/`: Lambda functions for image upload presigning, async inference, result fetching, and Gemini Q&A.
- `tests/`: Local unit and integration test suite using `pytest` and `moto`.

