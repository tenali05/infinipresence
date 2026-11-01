#!/bin/bash
# Startup script for the infiniPresence test VM (set as the instance's
# "startup-script" metadata by create-vm.sh). Runs as root on every boot.
#
# 1. Installs Docker, git and a swap file on first boot.
# 2. Installs /usr/local/bin/infinipresence-update and a systemd timer that
#    runs it every 3 minutes, so every push to the deployed branch on GitHub
#    goes live without anyone logging in to the VM.
# 3. Starts a deploy in the background (which builds images and starts the stack).
set -euo pipefail

if ! command -v docker >/dev/null || ! command -v git >/dev/null; then
  apt-get update
  apt-get install -y ca-certificates curl git jq
  curl -fsSL https://get.docker.com | sh
fi

if [ ! -f /swapfile ]; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
swapon -a || true

mkdir -p /opt/infinipresence

cat > /usr/local/bin/infinipresence-update <<'EOF'
#!/bin/bash
# Pulls the deployed branch and redeploys when it changed (or with --force).
set -euo pipefail
exec 9>/run/infinipresence-update.lock
flock -n 9 || { echo "update already running"; exit 0; }
md() { curl -sf -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1" || true; }
REPO=$(md app-repo); REPO=${REPO:-https://github.com/tenali05/infinipresence}
BRANCH=$(md app-branch); BRANCH=${BRANCH:-main}
SRC=/opt/infinipresence/src
[ -d "$SRC/.git" ] || git clone "$REPO" "$SRC"
git -C "$SRC" remote set-url origin "$REPO"
git -C "$SRC" fetch -q origin "$BRANCH"
NEW=$(git -C "$SRC" rev-parse FETCH_HEAD)
OLD=$(cat /opt/infinipresence/deployed-sha 2>/dev/null || true)
FORCE=${1:-}
[ -f /opt/infinipresence/force-deploy ] && FORCE=--force && rm -f /opt/infinipresence/force-deploy
if [ "$NEW" = "$OLD" ] && [ "$FORCE" != "--force" ]; then exit 0; fi
git -C "$SRC" checkout -q -f -B "$BRANCH" "$NEW"
# Copy the deploy script out of the checkout so a later pull can't change it mid-run.
cp "$SRC/deploy/vm-deploy.sh" /opt/infinipresence/vm-deploy.sh
{
  echo "=== deploy $BRANCH@${NEW:0:7} $(date -Is)"
  bash /opt/infinipresence/vm-deploy.sh "$NEW" && echo "$NEW" > /opt/infinipresence/deployed-sha
} 2>&1 | tr '\r' '\n' | grep --line-buffered -v 'Updating DocTypes' \
  | tee -a /var/log/infinipresence-deploy.log /dev/ttyS0
EOF
chmod 755 /usr/local/bin/infinipresence-update

cat > /etc/systemd/system/infinipresence-update.service <<'EOF'
[Unit]
Description=Deploy the latest infiniPresence code from GitHub
After=docker.service network-online.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/infinipresence-update
EOF
cat > /etc/systemd/system/infinipresence-update.timer <<'EOF'
[Unit]
Description=Check GitHub for infiniPresence changes every 3 minutes
[Timer]
OnBootSec=10min
OnUnitInactiveSec=3min
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now infinipresence-update.timer

# Deploy in its own systemd unit so the (long) first build isn't tied to the
# startup-script runner's lifetime.
touch /opt/infinipresence/force-deploy
systemctl start --no-block infinipresence-update.service
