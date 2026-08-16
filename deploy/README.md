# Deploying

One command on a fresh Ubuntu 24.04 server. Everything after that is filling in
credentials.

## 1. Reserve a static IP first

Not strictly required, but an ephemeral IP changes when the VM restarts, and the
hostname is derived from it — so the webhook URL you registered with Meta would
silently stop working. On Google Cloud: **VPC network → IP addresses → reserve
the external address** attached to the instance. It costs the same as the
ephemeral one.

## 2. Run the setup script

SSH into the server, then:

```sh
curl -fsSL https://raw.githubusercontent.com/prodigital97/Podcast-Cover-DMs/claude/podcast-cover-dm-drafts-l133n8/deploy/setup.sh -o setup.sh
sudo bash setup.sh <YOUR-IP>.sslip.io
```

Replace `<YOUR-IP>` with the server's external IP, dots and all — so
`34.30.1.2` becomes `34.30.1.2.sslip.io`. That's a free public DNS service that
resolves any `a.b.c.d.sslip.io` name to that IP, which is what lets Caddy get a
real HTTPS certificate without you owning a domain.

If you do own a domain, point an A record at the server and pass that instead:

```sh
sudo bash setup.sh dms.yourdomain.com
```

The script installs Python and Caddy, clones the repo, creates a locked-down
service user, writes a systemd unit, sets up a nightly database backup, and
obtains the certificate. Re-running it updates the code — it never overwrites
your credentials or database.

## 3. Fill in the credentials

```sh
sudo nano /etc/podcast-cover-dms/env
```

Every field is commented. The database path is already set. Then:

```sh
sudo systemctl start podcast-cover-dms
curl https://<your-hostname>/health
```

You should get `{"status":"ok"}`.

## 4. Register the webhooks

**Telegram** — from the server:

```sh
cd /opt/podcast-cover-dms
sudo -u dmbot .venv/bin/python scripts/set_telegram_webhook.py https://<your-hostname>
```

**Instagram** — in the Meta app dashboard, subscribe to the `messages` field on
the Instagram object with:

- Callback URL: `https://<your-hostname>/webhooks/instagram`
- Verify token: whatever you set as `IG_VERIFY_TOKEN`

## Where things live

| Path | What |
| --- | --- |
| `/opt/podcast-cover-dms` | The code. Replaced on every deploy. |
| `/etc/podcast-cover-dms/env` | Credentials. Never touched by a deploy. |
| `/var/lib/podcast-cover-dms/dms.sqlite3` | Leads, messages, approvals. |
| `/var/backups/podcast-cover-dms/` | Nightly snapshots, 14 days. |

Keeping the database and credentials outside the git tree is deliberate — it
means redeploying is always safe.

## Day-to-day

```sh
sudo journalctl -u podcast-cover-dms -f      # live logs
sudo systemctl restart podcast-cover-dms     # restart
sudo systemctl status podcast-cover-dms      # is it up
sudo bash /opt/podcast-cover-dms/deploy/setup.sh <hostname>   # deploy latest code
```

## Restoring a backup

```sh
sudo systemctl stop podcast-cover-dms
sudo gunzip -c /var/backups/podcast-cover-dms/dms-2026-08-20.sqlite3.gz \
  | sudo tee /var/lib/podcast-cover-dms/dms.sqlite3 >/dev/null
sudo chown dmbot:dmbot /var/lib/podcast-cover-dms/dms.sqlite3
sudo systemctl start podcast-cover-dms
```

The backups are only on the same disk as the server. Once there's real lead
history worth keeping, copy them somewhere else too.
