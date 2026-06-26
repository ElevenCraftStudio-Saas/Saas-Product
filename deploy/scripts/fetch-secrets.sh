#!/usr/bin/env bash
# Render the runtime .env from AWS Secrets Manager using the instance role.
# No static AWS keys are used or written. Run on the Docker host.
#
#   sudo deploy/scripts/fetch-secrets.sh           # uses /opt/wedfind/deploy.conf
#   APP_SECRET_NAME=... AWS_REGION=... ./fetch-secrets.sh   # override
set -euo pipefail

CONF=/opt/wedfind/deploy.conf
[ -f "$CONF" ] && . "$CONF"

: "${APP_SECRET_NAME:?APP_SECRET_NAME required (set in $CONF or env)}"
: "${AWS_REGION:?AWS_REGION required}"

OUT_DIR=${OUT_DIR:-/opt/wedfind}
ENV_FILE="$OUT_DIR/.env"
mkdir -p "$OUT_DIR"

echo "Fetching secret $APP_SECRET_NAME from $AWS_REGION ..."
JSON=$(aws secretsmanager get-secret-value \
  --secret-id "$APP_SECRET_NAME" \
  --region "$AWS_REGION" \
  --query SecretString --output text)

# Flatten the JSON object into KEY=VALUE lines. Values are emitted verbatim;
# the app's pydantic Settings validates/normalizes them at boot.
umask 077
{
  echo "# Generated $(date -u +%FT%TZ) from $APP_SECRET_NAME — DO NOT COMMIT"
  echo "$JSON" | jq -r 'to_entries[] | "\(.key)=\(.value)"'
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"

# Sanity: required keys must be present and non-empty.
required=(DATABASE_URL REDIS_URL AWS_REGION S3_BUCKET FIREBASE_PROJECT_ID)
missing=0
for k in "${required[@]}"; do
  if ! grep -qE "^${k}=.+" "$ENV_FILE"; then
    echo "ERROR: required key '$k' missing/empty in secret" >&2
    missing=1
  fi
done
# Firebase credentials must arrive one of two ways.
if ! grep -qE '^FIREBASE_SERVICE_ACCOUNT_B64=.+' "$ENV_FILE" \
   && ! grep -qE '^GOOGLE_APPLICATION_CREDENTIALS=.+' "$ENV_FILE"; then
  echo "WARNING: no Firebase service-account in secret (Admin SDK/Firestore will be disabled)." >&2
fi
[ "$missing" -eq 0 ] || { echo "fetch-secrets: validation failed" >&2; exit 1; }

echo "Wrote $ENV_FILE ($(grep -c '=' "$ENV_FILE") keys). Permissions:"
ls -l "$ENV_FILE"
