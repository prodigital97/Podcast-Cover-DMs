#!/usr/bin/env bash
# One-shot setup for a fresh Ubuntu 24.04 server.
#
#     sudo bash setup.sh <hostname>
#
# <hostname> is the public name the webhooks will hit, e.g.
#   34.30.1.2.sslip.io      (no domain needed — sslip.io resolves to the IP in the name)
#   dms.yourdomain.com      (if you own a domain and pointed an A record at this server)
#
# Installs Python and Caddy, creates a service user, clones the repo, writes a
# systemd unit and a nightly backup job, and gets an HTTPS certificate.
# Idempotent: safe to re-run.

set -euo pipefail

HOSTNAME_ARG="${1:-}"
REPO="https://github.com/prodigital97/Podcast-Cover-DMs.git"
BRANCH="claude/podcast-cover-dm-drafts-l133n8"
APP_USER="dmbot"
APP_DIR="/opt/podcast-cover-dms"
PORT=8000

if [[ -z "$HOSTNAME_ARG" ]]; then
    echo "usage: sudo bash setup.sh <hostname>" >&2
    echo "  e.g. sudo bash setup.sh 34.30.1.2.sslip.io" >&2
    exit 2
fi
if [[ $EUID -ne 0 ]]; then
    echo "run with sudo" >&2
    exit 1
fi

echo "==> Installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl gnupg nano \
    ca-certificates debian-keyring debian-archive-keyring apt-transport-https sqlite3

if ! command -v caddy >/dev/null; then
    echo "==> Installing Caddy (handles HTTPS certificates automatically)"
    # --yes --batch: a re-run after an interrupted first attempt must not stop
    # to ask "overwrite?" on a key file already sitting there.
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
        | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy
fi

echo "==> Creating service user"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"

echo "==> Fetching the code"
# After the first run this directory is owned by $APP_USER, not root. Without
# this, git refuses every subsequent `git fetch`/`git pull` run as root here —
# including this script's own re-run path — with "detected dubious ownership".
git config --global --get-all safe.directory 2>/dev/null | grep -qxF "$APP_DIR" \
    || git config --global --add safe.directory "$APP_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" fetch --quiet origin "$BRANCH"
    git -C "$APP_DIR" reset --hard --quiet "origin/$BRANCH"
else
    git clone --quiet --branch "$BRANCH" "$REPO" "$APP_DIR"
fi

echo "==> Installing Python dependencies"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# The database and .env live outside the git tree so a redeploy never touches them.
install -d -o "$APP_USER" -g "$APP_USER" -m 750 /var/lib/podcast-cover-dms
install -d -o root -g "$APP_USER" -m 750 /etc/podcast-cover-dms
if [[ ! -f /etc/podcast-cover-dms/env ]]; then
    install -o root -g "$APP_USER" -m 640 "$APP_DIR/.env.example" /etc/podcast-cover-dms/env
    sed -i 's|^DB_PATH=.*|DB_PATH=/var/lib/podcast-cover-dms/dms.sqlite3|' /etc/podcast-cover-dms/env
    echo "==> Wrote /etc/podcast-cover-dms/env from the template — fill it in before starting"
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> Writing the systemd service"
cat > /etc/systemd/system/podcast-cover-dms.service <<UNIT
[Unit]
Description=Podcast Cover DM drafting service
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=/etc/podcast-cover-dms/env
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=5

# The service needs nothing outside its own data directory.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/podcast-cover-dms

[Install]
WantedBy=multi-user.target
UNIT

echo "==> Configuring Caddy for $HOSTNAME_ARG"
cat > /etc/caddy/Caddyfile <<CADDY
$HOSTNAME_ARG {
	reverse_proxy 127.0.0.1:$PORT
}
CADDY

echo "==> Installing the nightly backup job"
install -m 755 "$APP_DIR/deploy/backup.sh" /usr/local/bin/dms-backup
cat > /etc/cron.d/podcast-cover-dms-backup <<CRON
# Nightly database snapshot, kept for 14 days.
30 3 * * * root /usr/local/bin/dms-backup >/dev/null 2>&1
CRON

systemctl daemon-reload
systemctl enable --quiet podcast-cover-dms
systemctl restart caddy

cat <<NEXT

────────────────────────────────────────────────────────────
Setup done. The service is installed but NOT started, because
it has no credentials yet.

  1. Fill in the environment file:
       sudo nano /etc/podcast-cover-dms/env

  2. Start it:
       sudo systemctl start podcast-cover-dms

  3. Check it came up:
       sudo systemctl status podcast-cover-dms
       curl https://$HOSTNAME_ARG/health

Your webhook URLs, for Meta and for the Telegram setup script:

  Instagram:  https://$HOSTNAME_ARG/webhooks/instagram
  Telegram:   https://$HOSTNAME_ARG/webhooks/telegram

Logs:   sudo journalctl -u podcast-cover-dms -f
Update: sudo bash $APP_DIR/deploy/setup.sh $HOSTNAME_ARG
────────────────────────────────────────────────────────────
NEXT
