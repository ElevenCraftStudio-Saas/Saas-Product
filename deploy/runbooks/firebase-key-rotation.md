# Runbook — Firebase Service-Account Key Rotation

**Why:** the previously committed/exposed service-account key must be treated as
compromised. Anyone holding it can mint admin credentials for the Firebase
project. Rotate **before** the staging host is internet-facing, and again before
production.

**Blast radius:** the key is used by the backend Admin SDK for Firestore (RBAC
roles) and any privileged Firebase calls. ID-token *verification* uses Google's
public certs and does **not** need this key — so token login keeps working even
mid-rotation. Firestore role reads degrade gracefully if the key is briefly
absent.

**Where the key lives now (target state):** only inside the Secrets Manager
secret `wedfind-<env>/app`, field `FIREBASE_SERVICE_ACCOUNT_B64`. Never in git,
never in Terraform state, never baked into the image.

---

## Procedure (zero-downtime)

### 1. Create a NEW key (GCP side)
Firebase console → Project settings → Service accounts → **Generate new private
key**. Save the JSON locally as `new-sa.json` (handle as a secret; delete after).

CLI alternative:
```bash
gcloud iam service-accounts keys create new-sa.json \
  --iam-account=firebase-adminsdk-xxxx@<project>.iam.gserviceaccount.com
```

### 2. Inject into Secrets Manager (does NOT touch GCP)
```bash
deploy/scripts/rotate-firebase-key.sh new-sa.json wedfind-staging/app ap-south-1
```
This base64-encodes the key and merges only the `FIREBASE_SERVICE_ACCOUNT_B64`
field into the secret (a new secret version).

### 3. Roll the app so it picks up the new key
On the host (via SSM Session Manager or SSH):
```bash
sudo deploy/scripts/deploy.sh <current-image-ref>
```
`deploy.sh` re-renders `.env` from the secret and restarts `api` + `worker` +
`beat`. The app decodes the b64 key, writes `/app/firebase-service-account.json`
(0600), and initializes the Admin SDK.

### 4. Verify (see validation-checklist.md for the full list)
```bash
# Admin SDK initialized with the new key:
docker compose -f /opt/wedfind/docker-compose.staging.yml logs api | grep -i "Firebase Admin initialized"
# Readiness still green:
docker compose -f /opt/wedfind/docker-compose.staging.yml exec -T api \
  curl -fsS -H 'X-Forwarded-Proto: https' http://localhost:8000/readyz
# A Firestore-backed path works (e.g. an admin endpoint that reads roles).
```

### 5. ONLY AFTER verifying — revoke the OLD key (GCP side)
```bash
gcloud iam service-accounts keys list \
  --iam-account=firebase-adminsdk-xxxx@<project>.iam.gserviceaccount.com
gcloud iam service-accounts keys delete <OLD_KEY_ID> \
  --iam-account=firebase-adminsdk-xxxx@<project>.iam.gserviceaccount.com
```

### 6. Clean up
```bash
shred -u new-sa.json   # or: rm -P new-sa.json
```
Confirm no copies remain in shell history, clipboard, or Slack/email.

---

## Rollback
If step 4 fails: the previous secret version still exists.
```bash
# List versions and restore the prior one to AWSCURRENT:
aws secretsmanager list-secret-version-ids --secret-id wedfind-staging/app --region ap-south-1
aws secretsmanager update-secret-version-stage --secret-id wedfind-staging/app \
  --version-stage AWSCURRENT --move-to-version-id <PREVIOUS_VERSION_ID> \
  --remove-from-version-id <NEW_VERSION_ID> --region ap-south-1
sudo deploy/scripts/deploy.sh <current-image-ref>   # re-render + restart
```
Do **not** delete the old GCP key until the new one is confirmed working.

## Cadence
Rotate every 90 days, on operator offboarding, or immediately on suspected
exposure. Track the next date in the team calendar.
