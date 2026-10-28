# AWS workflow

Read this file for every AWS task in this repository.

- Prefer the AWS MCP Server for AWS interactions because it provides sandboxed
  execution, observability, and audit logging. Use AWS CLI only when the MCP
  surface is unavailable.
- Load the relevant AWS skill before acting and prefer its current guidance over
  general knowledge.
- Verify uncertain AWS API parameters, permissions, limits, and error codes
  against official documentation instead of guessing.
- Prefer AWS CDK or CloudFormation over direct infrastructure mutation and
  follow AWS Well-Architected principles.
- Do not use em dashes in AWS resource names or descriptions.

## Secrets

- Load `aws-secrets-manager` before any secret, credential, API key, token, or
  password task. If that skill is unavailable, stop before handling the secret.
- Never call `secretsmanager get-secret-value` or `batch-get-secret-value` and
  never query the Secrets Manager Agent daemon directly.
- Resolve secrets only at runtime with
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` and `asm-exec` so
  secret values do not enter agent context.

