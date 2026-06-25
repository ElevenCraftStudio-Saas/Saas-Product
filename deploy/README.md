# WedFind — Operational Deployment (`deploy/`)

Infrastructure-as-Code + runbooks for a reproducible **staging** environment that
promotes to production by parameter change. **No application code lives here** —
the same backend image runs locally and in the cloud; only its environment and
surrounding infra differ.

## Layout
```
deploy/
  terraform/        IaC: VPC, subnets, SGs, EC2 host, RDS(pgvector), ElastiCache,
                    S3, IAM roles, Secrets Manager, CloudWatch, Route53
  compose/          docker-compose.staging.yml + Caddyfile (host runtime)
  scripts/          fetch-secrets.sh, deploy.sh, rollback.sh, rotate-firebase-key.sh
  env/              staging.env.template, secrets.example.json (shapes/reference)
  runbooks/         deployment, firebase-key-rotation, secrets-manager,
                    validation-checklist, monitoring, rollback
```

## Security model (read first)
- **No static AWS keys anywhere.** S3 access = EC2 **instance role** (boto3 auto).
- **Secrets in AWS Secrets Manager** (`wedfind-<env>/app`), rendered to a
  `600` `.env` on the host by `fetch-secrets.sh`. App reads the `.env` — it never
  calls Secrets Manager itself (clean boundary, app stays cloud-agnostic).
- **Firebase key + Sentry DSN** are injected out-of-band and are Terraform
  `ignore_changes` → they never enter Terraform state or git.
- **IMDSv2 required**, private subnets for RDS/Redis, SGs least-privilege
  (DB/Redis reachable only from the app host), S3 fully private + encrypted.
- **Access via SSM Session Manager** by default (no SSH port unless you opt in).

## Quickstart
1. **Build/push image** → `runbooks/deployment.md` §0
2. **`terraform apply`** (VPC→RDS→Redis→S3→EC2→Secrets→CloudWatch) → §1
3. **Inject Firebase key + Sentry** into the secret → §2 / `firebase-key-rotation.md`
4. **`deploy.sh <image>`** on the host (SSM) → §3
5. **Run `validation-checklist.md`** — every box green → §4
6. **DNS+TLS**, then **`npm run e2e` vs staging** until green → §5–6

## Priority-1 security tasks (do now)
- [ ] Rotate the exposed Firebase service-account key → `firebase-key-rotation.md`
- [ ] Confirm the old key is **deleted** in GCP after validation
- [ ] Verify no AWS static keys in any `.env` (validation-checklist §1)
- [ ] Subscribe ops to the alarms SNS topic

## Promotion to production
`terraform apply -var environment=production -var db_multi_az=true ...` with a
**separate** Firebase project, secret, and S3 bucket. Details in
`runbooks/deployment.md` → *Promotion to production*.

## Notes / assumptions
- Region defaults to `ap-south-1` (matches the existing `AWS_REGION`).
- pgvector ships with RDS Postgres 16; the app's Alembic migration runs
  `CREATE EXTENSION vector`.
- Terraform was authored but **not** applied/validated here (no AWS creds or TF
  binary in this workspace). Run `terraform validate` + `plan` before `apply`;
  review the plan for any destructive change to RDS/S3.
- Single-AZ NAT + single EC2 host in staging for cost. For prod HA: multi-AZ RDS
  (flag provided), a Redis replication group, and an ALB+ASG in front of ≥2 hosts.
