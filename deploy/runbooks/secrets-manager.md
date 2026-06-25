# Runbook — AWS Secrets Manager Integration

## Model
- **One secret per environment:** `wedfind-<env>/app` (JSON object).
- **Terraform seeds** the values it owns: `DATABASE_URL`, `REDIS_URL`,
  `AWS_REGION`, `S3_BUCKET`, `FIREBASE_PROJECT_ID`, `FRONTEND_URL`, `ENV`.
- **Injected out-of-band** (Terraform `ignore_changes`, never in state):
  `FIREBASE_SERVICE_ACCOUNT_B64`, `SENTRY_DSN`.
- **Not stored at all:** AWS access keys. The EC2 instance role grants S3; boto3
  reads role credentials automatically.

## How the app consumes it
1. EC2 boots with the instance profile (`*-app-role`) → has
   `secretsmanager:GetSecretValue` on this one secret only.
2. `deploy/scripts/fetch-secrets.sh` pulls the JSON and renders
   `/opt/wedfind/.env` (mode 600), one `KEY=VALUE` per field.
3. Compose passes `--env-file /opt/wedfind/.env` to `api`/`worker`/`beat`.
4. The app's pydantic `Settings` validates required keys at startup (fail-fast).

No application code reads Secrets Manager directly — the boundary is the rendered
`.env`. This keeps the app cloud-agnostic and unchanged.

## Common operations

Read the current secret:
```bash
aws secretsmanager get-secret-value --secret-id wedfind-staging/app \
  --region ap-south-1 --query SecretString --output text | jq .
```

Set / change a single field (e.g. SENTRY_DSN) without disturbing others:
```bash
SECRET=wedfind-staging/app; REGION=ap-south-1
CUR=$(aws secretsmanager get-secret-value --secret-id $SECRET --region $REGION --query SecretString --output text)
echo "$CUR" | jq --arg v 'https://...ingest.sentry.io/123' '.SENTRY_DSN=$v' \
  | aws secretsmanager put-secret-value --secret-id $SECRET --region $REGION --secret-string file:///dev/stdin
```

Rotate the Firebase key: see [firebase-key-rotation.md](firebase-key-rotation.md).

Rotate the DB password:
1. Change it on RDS (console or `aws rds modify-db-instance --master-user-password`).
2. Update `DATABASE_URL` in the secret (jq merge as above).
3. `sudo deploy/scripts/deploy.sh <image>` to re-render + restart.

After ANY secret change, re-run `deploy.sh` (or `fetch-secrets.sh` +
`docker compose restart`) so containers see the new `.env`.

## Access audit
Every read is logged in CloudTrail (`GetSecretValue`). Review periodically:
```bash
aws cloudtrail lookup-events --lookup-attributes \
  AttributeKey=ResourceName,AttributeValue=wedfind-staging/app --region ap-south-1
```
Only the app role and named operators should appear.
