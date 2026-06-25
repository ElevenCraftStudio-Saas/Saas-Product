#!/usr/bin/env bash
# Inject a NEW Firebase service-account key into Secrets Manager, then trigger a
# redeploy so the app picks it up. Does NOT touch GCP — create/delete the key in
# the Firebase console or via gcloud per the runbook. State (the key) never lives
# in Terraform: this script merges only the FIREBASE_SERVICE_ACCOUNT_B64 field.
#
#   ./rotate-firebase-key.sh <new-service-account.json> <app-secret-name> <region>
set -euo pipefail

KEY_FILE=${1:?path to new service-account JSON required}
SECRET_NAME=${2:?app secret name required (e.g. wedfind-staging/app)}
REGION=${3:-ap-south-1}

[ -f "$KEY_FILE" ] || { echo "no such file: $KEY_FILE" >&2; exit 1; }
jq -e .private_key "$KEY_FILE" >/dev/null || { echo "not a valid SA key (no private_key)" >&2; exit 1; }

echo "==> Base64-encoding new key"
B64=$(base64 -w0 "$KEY_FILE" 2>/dev/null || base64 "$KEY_FILE" | tr -d '\n')

echo "==> Merging FIREBASE_SERVICE_ACCOUNT_B64 into $SECRET_NAME"
CUR=$(aws secretsmanager get-secret-value --secret-id "$SECRET_NAME" --region "$REGION" --query SecretString --output text)
NEW=$(echo "$CUR" | jq --arg b "$B64" '.FIREBASE_SERVICE_ACCOUNT_B64 = $b')
aws secretsmanager put-secret-value --secret-id "$SECRET_NAME" --region "$REGION" --secret-string "$NEW" >/dev/null

echo "==> Secret updated. New version staged."
echo "Next:"
echo "  1. On the host: sudo deploy/scripts/deploy.sh <current-image-ref>   (re-renders .env, restarts app + worker)"
echo "  2. Verify:      curl -fsS http://localhost:8000/readyz   and check logs for 'Firebase Admin initialized'"
echo "  3. Only AFTER verifying, DELETE the OLD key in the Firebase console / gcloud."
