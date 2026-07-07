# EC2 → Fargate Migration Runbook

Moves the backend from the single EC2 host (`deploy/terraform/`) to the
serverless stack in `deploy/terraform-fargate/`: ECS Fargate + ALB/ACM +
Aurora Serverless v2 + ElastiCache. Both stacks coexist (separate VPCs,
10.20/16 vs 10.30/16) so this is a build-parallel-then-cutover migration with
minutes of read-only time, not hours of downtime.

**Prerequisite already shipped:** SSE state is Redis-backed
(`app/services/processing_state.py`, commit 79175c2) — multiple API tasks are
safe.

**Celery/Redis caveat:** ElastiCache **Serverless** speaks the Redis cluster
protocol, which Celery (kombu) does not support. The stack therefore defaults
to `redis_mode = "node"` (one cache.t4g.micro). Choose `serverless` only after
migrating the Celery broker to SQS (follow-up task; requires `kombu[sqs]` and
`broker_url = "sqs://"`).

---

## 0. Prereqs

- AWS CLI authenticated, region `us-east-1`
- Terraform ≥ 1.6
- Docker (to build/push the image)
- Access to DNS (Hostinger) for the `api.` record

## 1. Build + push the image to ECR

```bash
cd deploy/terraform-fargate
terraform init && terraform apply -target=aws_ecr_repository.backend

ECR=$(terraform output -raw ecr_repository_url)
TAG=$(date +%Y%m%d)-$(git rev-parse --short HEAD)

aws ecr get-login-password | docker login --username AWS --password-stdin "${ECR%%/*}"
docker build -t "$ECR:$TAG" ../../backend
docker push "$ECR:$TAG"
```

## 2. Apply the full stack

```bash
cp terraform.tfvars.example terraform.tfvars   # edit: db_password, app_domain, backend_image_tag=$TAG
terraform apply
```

First apply takes ~15 min (Aurora). ECS services will start but the API tasks
crash-loop until step 3-4 (placeholder secrets) — expected.

## 3. Fill in the secret placeholders

Console → Secrets Manager → `wedfind-<env>-fargate/app`:

- `SECRET_KEY`: `openssl rand -hex 32` (signs guest download tokens)
- `FIREBASE_SERVICE_ACCOUNT_B64`: `base64 -w0 firebase-service-account.json`
- `SENTRY_DSN`: if used

Then force new deployments: `aws ecs update-service --cluster <cluster> --service api --force-new-deployment` (same for worker/beat).

## 4. Validate the ACM cert + point DNS

```bash
terraform output acm_validation_records   # create these CNAMEs in Hostinger
# wait: aws acm describe-certificate ... Status == ISSUED
terraform output alb_dns_name             # note for step 6
```

## 5. Migrate the database (RDS → Aurora)

Aurora PG 16 supports pgvector. From any machine that can reach both
(temporarily allow your IP on both DB security groups, or run via SSM on the
old EC2 host):

```bash
# 1. Stop writes: scale down old API (docker compose stop api worker beat via SSM)
# 2. Dump old RDS
pg_dump "postgresql://wedfind:<old_pw>@wedfind-db.....rds.amazonaws.com:5432/wedfind" \
  --no-owner --no-privileges -Fc -f wedfind.dump
# 3. Restore into Aurora (endpoint: terraform output aurora_endpoint)
pg_restore -d "postgresql://wedfind:<new_pw>@<aurora-endpoint>:5432/wedfind" \
  --no-owner --no-privileges wedfind.dump
# 4. Bring schema to head (new image includes migrations the old RDS lacked —
#    thumb_key, FK cascades, HNSW index):
aws ecs run-task ... --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'
#    (or exec into a running api task: aws ecs execute-command)
```

S3: keep using the existing photos bucket — set `S3_BUCKET` in the new secret
to the old bucket name and grant the task role access, or sync:
`aws s3 sync s3://<old-bucket> s3://wedfind-<env>-fg-photos`.

## 6. Cutover

1. Smoke test via ALB directly: `curl -H "Host: api.<domain>" https://<alb_dns>/readyz` → 200
2. DNS: change `api.<domain>` from the EC2 Elastic IP (A record) to a CNAME →
   `alb_dns_name`
3. Watch: CloudWatch `/wedfind/<env>-fargate/app` logs + target-group health
4. Full guest-flow test: QR → consent → selfie → SSE progress → gallery →
   download (exercises Redis SSE state + signed tokens end-to-end)

## 7. Decommission the EC2 stack (after a quiet week)

```bash
cd ../terraform
terraform destroy   # removes EC2, EIP, old RDS, old Redis — snapshot RDS first:
# aws rds create-db-snapshot --db-instance-identifier wedfind-staging-pg --db-snapshot-identifier wedfind-pre-fargate
```

Keep the old S3 bucket if step 5 pointed the new stack at it.

## Rollback (any point before DNS TTL settles)

Point `api.` DNS back at the EC2 Elastic IP. The old host is untouched until
step 7. Data written to Aurora after cutover would need a reverse dump.

## Cost sketch (staging, us-east-1, rough)

| Item | ~$/mo |
|---|---|
| Fargate: api 2×(0.5 vCPU/1 GB) + worker (2 vCPU/6 GB) + beat | 90-110 |
| ALB | 17 + traffic |
| Aurora Sv2 0.5-4 ACU (mostly ~0.5) | 45-60 |
| ElastiCache t4g.micro | 12 |
| NAT | 33 + traffic |
| vs current EC2 t3.large + RDS t3.small + Redis | ~95-110 |

Fargate stack runs slightly higher at idle but removes the host as a single
point of failure and scales the API automatically. Trim by dropping
`api_desired_count` to 1 in staging.
