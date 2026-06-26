#!/usr/bin/env bash
# Roll out (or update) the WedFind stack on the Docker host.
#   sudo deploy/scripts/deploy.sh <image-ref>
# e.g. deploy.sh 123456789012.dkr.ecr.ap-south-1.amazonaws.com/wedfind-backend:2026-06-25
#
# Steps: fetch secrets -> pull image -> compose up -> migrate -> health gate.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
APP_DIR=/opt/wedfind
COMPOSE_FILE="$APP_DIR/docker-compose.staging.yml"
CONF="$APP_DIR/deploy.conf"
[ -f "$CONF" ] && . "$CONF"

IMAGE_REF=${1:-${BACKEND_IMAGE:-}}
: "${IMAGE_REF:?usage: deploy.sh <image-ref>}"

# Stage the compose file + Caddyfile into APP_DIR (first run or update).
install -m 0644 "$HERE/../compose/docker-compose.staging.yml" "$COMPOSE_FILE"
install -m 0644 "$HERE/../compose/Caddyfile" "$APP_DIR/Caddyfile"
export APP_DOMAIN=${APP_DOMAIN:-:80} # for compose interpolation (Caddy)

echo "==> Recording current image for rollback"
PREV_IMAGE=$(grep -E '^BACKEND_IMAGE=' "$APP_DIR/.deploy-state" 2>/dev/null | cut -d= -f2- || true)
echo "PREV_IMAGE=${PREV_IMAGE:-none}"

echo "==> Fetching secrets"
"$HERE/fetch-secrets.sh"

echo "==> Pulling image $IMAGE_REF"
# ECR login if the ref looks like an ECR registry.
if [[ "$IMAGE_REF" == *.dkr.ecr.*.amazonaws.com/* ]]; then
  REGISTRY=${IMAGE_REF%%/*}
  aws ecr get-login-password --region "${AWS_REGION:?}" | docker login --username AWS --password-stdin "$REGISTRY"
fi
docker pull "$IMAGE_REF"

echo "==> Starting stack"
export BACKEND_IMAGE="$IMAGE_REF"
docker compose -f "$COMPOSE_FILE" --env-file "$APP_DIR/.env" up -d

echo "==> Waiting for API health (/livez then /readyz)"
# api:8000 is not published to the host (only Caddy is), so probe inside the
# container. The forwarded header makes the prod app return a real status code.
probe() { docker compose -f "$COMPOSE_FILE" exec -T api \
  curl -fsS -H 'X-Forwarded-Proto: https' "http://localhost:8000/$1" >/dev/null 2>&1; }

ok=0
for i in $(seq 1 30); do
  if probe livez; then ok=1; break; fi
  sleep 5
done
[ "$ok" -eq 1 ] || { echo "API did not become live; see: docker compose -f $COMPOSE_FILE logs api" >&2; exit 1; }

# /readyz checks DB + Redis + S3 (migrations applied by the api command).
for i in $(seq 1 12); do
  if probe readyz; then
    echo "==> READY"
    # Record the image we are replacing as the rollback target, then commit new.
    echo "PREV_IMAGE=${PREV_IMAGE:-none}" > "$APP_DIR/.deploy-state.prev"
    echo "BACKEND_IMAGE=$IMAGE_REF" > "$APP_DIR/.deploy-state"
    docker image prune -f >/dev/null 2>&1 || true
    exit 0
  fi
  sleep 5
done

echo "API live but not ready (DB/Redis?). Logs:" >&2
docker compose -f "$COMPOSE_FILE" logs --tail=50 api >&2
exit 1
