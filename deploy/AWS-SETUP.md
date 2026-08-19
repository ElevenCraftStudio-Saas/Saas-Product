# WedFind AWS Setup — Recreate on a Fresh Account

Everything needed to stand WedFind back up on a **new AWS account** (the old one's
credits ran out). Two deploy shapes are documented: **lite** (one cheap EC2, ~$36/mo,
recommended for testing) and **Fargate** (serverless, ~$250-300/mo, for real event load).

> Nothing here is AWS-account-specific except the account ID that gets baked into
> resource names at apply time. All infra is Terraform — no click-ops required.

---

## 0. Prerequisites (on your PC)

| Tool | Why |
|---|---|
| AWS CLI v2 | drive the account |
| Terraform ≥ 1.6 | provision infra |
| Docker Desktop | build/push the backend image |
| Git | the repo |

Files you must have locally (NOT in git — kept private):
- `backend/firebase-service-account.json` — Firebase Admin SDK key
- Your Firebase project id (currently `saas-139a7`)

---

## 1. New AWS account bootstrap

1. Create the AWS account, log in as root, then **create an IAM admin user** (don't use root for daily work).
2. Give it programmatic access → get **Access Key ID + Secret**.
3. Configure the CLI:
   ```bash
   aws configure
   # paste key + secret, region = us-east-1, output = json
   ```
4. Verify: `aws sts get-caller-identity` → shows the new account id.

> **Free credits:** new accounts get 12-month Free Tier. Also complete the
> **"Explore AWS" console tasks** (Billing → Credits) — each grants ~$20. That's
> how the old account got its credits.

---

## 2. Services WedFind uses

| Service | Role | Lite | Fargate |
|---|---|---|---|
| EC2 | app host | ✅ 1× t3.medium | ❌ |
| ECS Fargate | serverless containers | ❌ | ✅ api/worker/beat |
| ALB + ACM | HTTPS load balancer + cert | ❌ (Caddy instead) | ✅ |
| Aurora Serverless v2 / Postgres | database (pgvector) | ❌ (container) | ✅ |
| ElastiCache Redis | Celery broker + SSE state | ❌ (container) | ✅ |
| S3 | photo + thumbnail storage | ✅ | ✅ |
| ECR | backend Docker image registry | ✅ | ✅ |
| Secrets Manager | app secrets | (host .env) | ✅ |
| IAM | instance/task roles | ✅ | ✅ |

**Not AWS but required:** Firebase (auth + Firestore roles). Unchanged across accounts —
same `saas-139a7` project, same service-account json. No migration needed.

---

## 3. LITE deploy (recommended — ~$36/mo, or $0 while stopped)

One t3.medium running the whole stack via docker-compose (Postgres + Redis as
containers, Caddy auto-HTTPS, S3 real). Code: `deploy/terraform-lite/`.

### 3.1 Build + push the image
```bash
cd deploy/terraform-lite
terraform init
# create the ECR repo first (or let step 3.2 make it):
aws ecr create-repository --repository-name wedfind-backend --region us-east-1

ECR=$(aws ecr describe-repositories --repository-name wedfind-backend --query 'repositories[0].repositoryUri' --output text)
TAG=$(date +%Y%m%d)-$(git rev-parse --short HEAD)
aws ecr get-login-password | docker login --username AWS --password-stdin ${ECR%%/*}
# IMPORTANT: build from repo root with -f (Dockerfile COPYs backend/):
docker build -f backend/Dockerfile -t "$ECR:$TAG" .
docker push "$ECR:$TAG"
```

### 3.2 Provision the box
```bash
terraform apply       # creates EC2, EIP, SG, IAM, S3 bucket (~2 min)
terraform output      # note public_ip, s3_bucket
```

### 3.3 Bootstrap the app on the host (via SSM, no SSH)
The host needs `/opt/wedfind/.env`, `docker-compose.yml`, and `Caddyfile`, then
`docker compose up -d` + `alembic upgrade head`. Template files:
- `deploy/compose/docker-compose.lite.yml`
- `deploy/compose/Caddyfile.lite`
- `deploy/env/lite.env.template`

**Secrets to generate for the host `.env`:**
| Key | How |
|---|---|
| `DB_PASSWORD` | `openssl rand -hex 12` (used by pg container + DATABASE_URL) |
| `SECRET_KEY` | `openssl rand -hex 32` (signs guest download tokens) |
| `FIREBASE_SERVICE_ACCOUNT_B64` | `base64 -w0 backend/firebase-service-account.json` |
| `S3_BUCKET` / `AWS_BUCKET_NAME` | `terraform output s3_bucket` (BOTH keys — s3_service reads the legacy name) |
| `BACKEND_IMAGE` | the `$ECR:$TAG` from 3.1 |
| `FIREBASE_PROJECT_ID` | `saas-139a7` |

Push all three files via `aws ssm send-command` (AWS-RunShellScript), then:
```bash
cd /opt/wedfind
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ecr-host>
docker compose --env-file .env up -d
docker compose --env-file .env run --rm api alembic upgrade head
```

### 3.4 DNS + HTTPS
- Point `api.wedfind.elevencraftstudio.com` **A record** → the EIP (`terraform output public_ip`)
- Delete any conflicting CNAME for the same name first
- Caddy auto-issues the Let's Encrypt cert on first HTTPS hit (~30s after DNS resolves)
- Verify: `curl https://api.wedfind.elevencraftstudio.com/readyz` → `{"status":"ok",...}`

### 3.5 First admin
DB starts empty. Log in once at the frontend → `/auth/me` auto-creates your user;
Firestore already has your role=admin doc, syncs on login. (Or run
`backend/scripts/make_admin_firestore.py <email>`.)

### Cost control
- Stop when idle: `aws ec2 stop-instances --instance-ids <id>` → ~$0.20/day, same IP on restart
- Start: `aws ec2 start-instances --instance-ids <id>` → containers auto-start, cert already on disk

---

## 4. FARGATE deploy (for real events — ~$250-300/mo, auto-scales)

Full serverless stack. Code: `deploy/terraform-fargate/`. Runbook:
`deploy/runbooks/fargate-migration.md` (covers image push, secret fill, ACM
validation, Aurora migration, DNS cutover).

Key gotchas learned in production (already baked into the terraform):
- **api_memory = 4096** — 2 gunicorn workers each load InsightFace; 1 GB OOM-loops
- **AWS_BUCKET_NAME** must be injected alongside S3_BUCKET (s3_service reads legacy name)
- **Redis = node mode**, NOT serverless — Celery/kombu can't speak the cluster protocol.
  ElastiCache Serverless needs the Celery broker moved to SQS first.
- ALB idle_timeout ≥ 120s so SSE streams aren't cut
- `/metrics` is public through the ALB — add a listener rule to 403 it (Caddy does this in lite)

Only choose Fargate for an actual paying event (3000-10000 photos need parallel
workers). Spin up for the event, `terraform destroy` after.

---

## 5. Secrets checklist (both stacks)

| Secret | Source | Notes |
|---|---|---|
| `DATABASE_URL` | generated | lite: `...@db:5432`; fargate: Aurora endpoint |
| `REDIS_URL` | generated | lite: `redis://redis:6379/0` |
| `S3_BUCKET` + `AWS_BUCKET_NAME` | terraform output | both required |
| `AWS_REGION` | `us-east-1` | |
| `FIREBASE_PROJECT_ID` | `saas-139a7` | |
| `FIREBASE_SERVICE_ACCOUNT_B64` | base64 of the json | never commit the json |
| `SECRET_KEY` | `openssl rand -hex 32` | set it, or download tokens die on restart |
| `SENTRY_DSN` | optional | error tracking |

AWS S3 access itself uses the **instance/task IAM role** — no static AWS keys in the app.

---

## 6. Teardown (leaving an account)

```bash
# lite:
cd deploy/terraform-lite && terraform destroy
# fargate:
cd deploy/terraform-fargate && terraform destroy
# manual leftovers (if any): empty + delete S3 buckets, delete ECR repo, release EIPs
```
Versioned buckets need object versions purged before delete (boto3
`bucket.object_versions.delete()`).

---

## 7. DNS records reference (Hostinger — elevencraftstudio.com)

| Record | Points to |
|---|---|
| `api.wedfind` A | lite EIP (or Fargate ALB via CNAME) |
| Frontend | Firebase Hosting (`www` CNAME → `*.web.app`) |

Clean up dead records when switching stacks (old ALB CNAMEs, ACM validation CNAMEs).

---

## Quick reference — what the old account had
- Account: 803992933859 (subashkaran912@gmail.com) — **being abandoned, credits exhausted**
- Region: us-east-1
- Lite instance: i-0cc35de110a77fdc9 @ EIP 44.215.195.58
- ECR image last built: `20260707-5357cb5`
- Firebase project: `saas-139a7` (KEEP — not AWS, works across accounts)
