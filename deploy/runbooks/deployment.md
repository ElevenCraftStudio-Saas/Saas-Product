# Runbook — Staging Deployment (reproducible, promotable to prod)

End-to-end. Assumes an AWS account, an IAM principal with admin (or scoped infra)
rights, a Firebase project, and a built backend image.

## Prerequisites
- Terraform/OpenTofu ≥ 1.6, AWS CLI v2, Docker, `jq`.
- A container registry the host can pull from (ECR recommended).
- DNS hosted zone (optional, for a real domain + TLS).

## 0. Build + push the backend image
```bash
# From repo root. Tag with a date/sha for traceability + rollback.
TAG=$(date -u +%Y%m%d)-$(git rev-parse --short HEAD)
aws ecr create-repository --repository-name wedfind-backend --region ap-south-1 || true
REG=<acct>.dkr.ecr.ap-south-1.amazonaws.com
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin $REG
docker build -f backend/Dockerfile -t $REG/wedfind-backend:$TAG .
docker push $REG/wedfind-backend:$TAG
```

## 1. Provision infrastructure
```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars   # set firebase_project_id, frontend_url, etc.
terraform init
terraform plan -out tf.plan                     # REVIEW: no unexpected destroys
terraform apply tf.plan
```
Outputs: `app_public_ip`, `app_instance_id`, `app_secret_name`, `s3_bucket`,
`rds_endpoint`, `redis_endpoint`, `alarms_sns_topic_arn`.

## 2. Configure secrets
Terraform already seeded DB/Redis/region/bucket/project. Now inject the rest:
```bash
# Firebase key (also the rotation path — see firebase-key-rotation.md):
deploy/scripts/rotate-firebase-key.sh new-sa.json $(terraform output -raw app_secret_name) ap-south-1
# Sentry DSN (optional): jq-merge into the secret (see secrets-manager.md).
```
Subscribe to alarms:
```bash
aws sns subscribe --topic-arn $(terraform output -raw alarms_sns_topic_arn) \
  --protocol email --notification-endpoint ops@wedfind.ai
```

## 3. Deploy the Docker stack
The host bootstrapped Docker + CloudWatch agent via user-data. Push the app:
```bash
INSTANCE=$(terraform output -raw app_instance_id)
aws ssm start-session --target $INSTANCE      # or SSH if enabled
# On the host (clone the repo or copy deploy/ over), then:
sudo deploy/scripts/deploy.sh <registry>/wedfind-backend:<TAG>
```
`deploy.sh` → fetch-secrets → pull → `compose up` (api+worker+beat+caddy) →
`alembic upgrade head` (in api start) → health gate on `/readyz`.

> First boot also creates the pgvector extension via the app's migrations
> (`CREATE EXTENSION vector`). RDS Postgres 16 includes it.

## 4. Validate
Run the full [validation-checklist.md](validation-checklist.md). Do not proceed
until every box is green.

## 5. DNS + TLS (if using a domain)
Set `app_domain` + `route53_zone_id` in tfvars and `terraform apply` (creates the
A record → EIP). Caddy obtains a Let's Encrypt cert automatically on first hit.
Verify: `curl -fsS https://<domain>/livez`.

## 6. Run the E2E suite against staging
Per Increment 8:
```bash
cd frontend
cp e2e/.env.e2e.example .env.e2e   # E2E_BASE_URL=https://<staging-frontend>, real studio creds, event slug
npm run e2e
```
Iterate until consistently green. This is the gate before production promotion.

## Promotion to production
The same code, parameterized:
```bash
cd deploy/terraform
terraform workspace new production           # or a separate state key/dir
terraform apply -var environment=production -var db_multi_az=true \
  -var db_instance_class=db.t3.medium -var app_instance_type=t3.xlarge
```
`environment=production` flips: deletion protection on, final snapshot on, longer
secret recovery window, Redis snapshots. Use a SEPARATE Firebase project + secret
+ S3 bucket for prod. Re-run secrets + deploy + validation against prod.

## What changes vs local docker-compose.yml
- Managed RDS + ElastiCache (no db/redis containers).
- S3 via instance role (no AWS keys in env).
- Caddy TLS front; uvicorn proxy-aware.
- Image pulled, not built; secrets from Secrets Manager.
- **No application code differs.** Same image runs locally and in staging/prod.
