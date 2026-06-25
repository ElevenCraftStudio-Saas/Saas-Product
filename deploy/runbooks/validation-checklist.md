# Validation Checklist — App Starts Correctly with Rotated Credentials

Run after the first deploy and after every secret/key rotation. All commands run
on the host (SSM: `aws ssm start-session --target <instance-id>`).

Set once:
```bash
C="docker compose -f /opt/wedfind/docker-compose.staging.yml"
H="-H X-Forwarded-Proto:https"   # makes the prod app return real status (no 307)
```

## 1. Secret rendered correctly
- [ ] `.env` exists, mode `600`, owned by root:
      `ls -l /opt/wedfind/.env`
- [ ] Required keys present + non-empty:
      `grep -E '^(DATABASE_URL|REDIS_URL|AWS_REGION|S3_BUCKET|FIREBASE_PROJECT_ID)=' /opt/wedfind/.env`
- [ ] No AWS static keys leaked in:
      `! grep -qE '^AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY)=' /opt/wedfind/.env && echo OK`
- [ ] Firebase key present:
      `grep -q '^FIREBASE_SERVICE_ACCOUNT_B64=.\+' /opt/wedfind/.env && echo OK`

## 2. Containers healthy
- [ ] All up: `$C ps` → `api`, `worker`, `beat`, `caddy` all `running`/`healthy`
- [ ] No crash loop: `$C logs --tail=50 api | grep -iE 'traceback|validationerror'` → empty

## 3. App boot + credentials
- [ ] Config validated (no fail-fast): `$C logs api | grep -i 'Application startup complete'`
- [ ] Firebase Admin initialized with the (new) key:
      `$C logs api | grep -i 'Firebase Admin initialized'`
- [ ] Firestore client ready:
      `$C logs api | grep -i 'Firestore client ready'`
- [ ] The decoded key file is private:
      `$C exec -T api sh -c 'ls -l /app/firebase-service-account.json'` → `-rw------- (600)`

## 4. Health endpoints (real status, not redirect)
- [ ] Live:  `$C exec -T api curl -fsS $H http://localhost:8000/livez`
- [ ] Ready (DB+Redis+S3): `$C exec -T api curl -fsS $H http://localhost:8000/readyz`
- [ ] Metrics exposed: `$C exec -T api curl -fsS http://localhost:8000/metrics | head -1`

## 5. Dependencies reachable
- [ ] DB migrations at head:
      `$C exec -T api alembic current` → shows the latest revision
- [ ] Redis/Celery: `$C exec -T worker celery -A app.workers.celery_app inspect ping`
- [ ] S3 via instance role (no keys): app `/readyz` S3 check passes (covered above);
      sanity: `$C exec -T api python -c "import boto3,os;print(boto3.client('s3').list_objects_v2(Bucket=os.environ['S3_BUCKET'],MaxKeys=1).get('ResponseMetadata',{}).get('HTTPStatusCode'))"` → `200`

## 6. External path (through Caddy/TLS)
- [ ] Domain resolves to the EIP: `dig +short $APP_DOMAIN`
- [ ] HTTPS works + valid cert: `curl -fsS https://$APP_DOMAIN/livez`
- [ ] HTTP redirects to HTTPS: `curl -sI http://$APP_DOMAIN/livez | grep -i location`

## 7. Auth smoke (token verification unaffected by rotation)
- [ ] A real Firebase ID token verifies (login via the frontend, or hit an
      authenticated endpoint with a fresh token) → 200, not 401.

## 8. Observability
- [ ] Logs flowing to CloudWatch group `/wedfind/<env>/app`
- [ ] Sentry receiving events (if `SENTRY_DSN` set): trigger a test error, confirm in Sentry
- [ ] Alarms in `OK` state: `aws cloudwatch describe-alarms --alarm-name-prefix wedfind-<env>`

**Gate:** do not delete the old Firebase key (rotation step 5) or proceed to beta
until every box above is checked.
