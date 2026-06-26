#!/usr/bin/env bash
# Roll the stack back to the previously deployed image. Relies on the
# .deploy-state breadcrumb written by deploy.sh.
#   sudo deploy/scripts/rollback.sh [image-ref]
# With no arg, rolls back to the image recorded BEFORE the current one.
set -euo pipefail

APP_DIR=/opt/wedfind
COMPOSE_FILE="$APP_DIR/docker-compose.staging.yml"
. "$APP_DIR/deploy.conf"

TARGET=${1:-}
if [ -z "$TARGET" ]; then
  TARGET=$(grep -E '^PREV_IMAGE=' "$APP_DIR/.deploy-state.prev" 2>/dev/null | cut -d= -f2- || true)
fi
: "${TARGET:?no rollback target — pass an image ref explicitly}"
[ "$TARGET" != "none" ] || { echo "no previous image recorded" >&2; exit 1; }

echo "==> Rolling back to $TARGET"
"$(dirname "$0")/fetch-secrets.sh"   # secrets unchanged, but re-render to be safe
if [[ "$TARGET" == *.dkr.ecr.*.amazonaws.com/* ]]; then
  aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${TARGET%%/*}"
fi
docker pull "$TARGET"

export BACKEND_IMAGE="$TARGET"
docker compose -f "$COMPOSE_FILE" --env-file "$APP_DIR/.env" up -d

for i in $(seq 1 30); do
  docker compose -f "$COMPOSE_FILE" exec -T api \
    curl -fsS -H 'X-Forwarded-Proto: https' http://localhost:8000/readyz >/dev/null 2>&1 \
    && { echo "==> Rollback healthy ($TARGET)"; exit 0; }
  sleep 5
done
echo "Rollback target unhealthy — investigate: docker compose -f $COMPOSE_FILE logs api" >&2
exit 1
