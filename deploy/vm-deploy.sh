#!/bin/bash
# Builds and (re)starts the infiniPresence stack on the VM. Called by
# /usr/local/bin/infinipresence-update with the commit SHA to deploy.
set -euo pipefail
SHA=${1:?commit sha}
TAG=${SHA:0:12}
STATE=/opt/infinipresence
SRC=$STATE/src
cd "$STATE"

md() { curl -sf -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/$1" || true; }
IP=$(md network-interfaces/0/access-configs/0/external-ip)
DOMAIN="${IP//./-}.sslip.io"
SITE="$DOMAIN"

if [ ! -f secrets.env ]; then
  echo "DB_PASSWORD=$(openssl rand -hex 16)" > secrets.env
  chmod 600 secrets.env
fi
. ./secrets.env
ADMIN_PASSWORD=$(md attributes/admin-password)
ADMIN_PASSWORD=${ADMIN_PASSWORD:-$DB_PASSWORD}

# 1. Base image: Frappe + ERPNext + HRMS (version-15). Built once, about 20 minutes.
FRAPPE_DOCKER_REF=61d35da827ebc04d01b64c9e78385597ccebc9d8
if ! docker image inspect infinipresence-base:v15 >/dev/null 2>&1; then
  echo "Building base image (first boot only)..."
  rm -rf frappe_docker
  git clone -q https://github.com/frappe/frappe_docker frappe_docker
  git -C frappe_docker checkout -q "$FRAPPE_DOCKER_REF"
  jq '[.[] | select(.url | test("infinipresence") | not)]' "$SRC/deploy/apps.json" > base-apps.json
  DOCKER_BUILDKIT=1 docker build \
    --build-arg FRAPPE_BRANCH=version-15 \
    --secret id=apps_json,src=base-apps.json \
    -t infinipresence-base:v15 \
    -f frappe_docker/images/layered/Containerfile frappe_docker
fi

# 2. App image: base + this repo. Rebuilt on every new commit, about a minute.
if ! docker image inspect "infinipresence-app:$TAG" >/dev/null 2>&1; then
  docker build -t "infinipresence-app:$TAG" -f "$SRC/deploy/Dockerfile.app" "$SRC"
fi

cat > stack.env <<EOF
IMAGE=infinipresence-app:$TAG
DOMAIN=$DOMAIN
DB_PASSWORD=$DB_PASSWORD
EOF
DC="docker compose -p infinipresence -f $SRC/deploy/compose.yml --env-file stack.env"
$DC up -d --remove-orphans
bench() { $DC exec -T backend bench "$@"; }

for i in $(seq 60); do $DC exec -T backend true 2>/dev/null && break; sleep 5; done

# 3. Site: create on first deploy, migrate afterwards.
if ! $DC exec -T backend test -d "sites/$SITE"; then
  echo "Creating site $SITE..."
  bench new-site "$SITE" --mariadb-user-host-login-scope='%' \
    --admin-password "$ADMIN_PASSWORD" --db-root-username root --db-root-password "$DB_PASSWORD" \
    --install-app erpnext --install-app hrms --install-app infinipresence --set-default
  bench --site "$SITE" set-config host_name "https://$DOMAIN"
else
  bench --site "$SITE" list-apps | grep -q infinipresence || bench --site "$SITE" install-app infinipresence
  bench --site "$SITE" migrate
fi
bench --site "$SITE" set-admin-password "$ADMIN_PASSWORD"
bench --site "$SITE" enable-scheduler

# 4. Sample data, once.
if [ ! -f demo-loaded ]; then
  echo "Loading sample data..."
  bench --site "$SITE" execute infinipresence.demo.setup.run
  bench --site "$SITE" execute infinipresence.demo.data.run
  # The setup wizard user is created with a well-known password; replace it.
  bench --site "$SITE" execute frappe.utils.password.update_password \
    --kwargs "{\"user\": \"admin@example.com\", \"pwd\": \"$ADMIN_PASSWORD\"}"
  touch demo-loaded
fi

# Keep only the running app image and the base image.
docker image ls --format '{{.Repository}}:{{.Tag}}' | grep '^infinipresence-app:' \
  | grep -v ":$TAG$" | xargs -r docker image rm >/dev/null 2>&1 || true
docker builder prune -af >/dev/null 2>&1 || true

echo "READY https://$DOMAIN (commit $TAG)"
