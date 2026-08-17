# Handoff — Podcast Cover DM bot

Status as of the last commit on `claude/podcast-cover-dm-drafts-l133n8`. Written
so a fresh session (human or AI) can pick this up with zero prior context.

## What this project is

Instagram DMs arrive → the server drafts three reply options with an LLM →
drafts land as an approval card in Telegram → a human taps Send/Edit/Redraft/Skip
→ the approved text goes back to Instagram. Nothing is ever sent to Instagram
without an explicit human tap — there is no autonomous-send code path at all.

The full design rationale, the prompt's strategy rules, and the architecture
are in `README.md` at the repo root. Read that first if this file raises
questions it doesn't answer.

---

## Done

### Code (all committed, all tested)

- **The drafting prompt and strategy rules** — `prompts/dm-reply.md`. Pitch
  timing, tone matching, soft-no handling. This is the actual product; treat
  changes to it as the highest-stakes edits in the repo.
- **FastAPI service** — `app/main.py` and friends. Instagram webhook (HMAC
  signature verified), Telegram webhook (shared-secret verified), the
  approval flow, SQLite storage for leads/messages/approvals.
- **Swappable model backend** — `app/providers.py`. `LLM_PROVIDER=anthropic`
  or `gemini` in the env file; both use native structured outputs so a bad
  reply fails the call rather than reaching the approval card.
- **48 tests, all passing, no credentials needed**: `python3 -m pytest tests -q`
- **Deploy tooling** — `deploy/setup.sh` (one-shot Ubuntu setup: Python, Caddy
  for automatic HTTPS, systemd service, nightly SQLite backup) and
  `deploy/gcloud-create-vm.sh` (creates the free-tier GCP VM in one command).
  Full runbook: `deploy/README.md`.
- **Standalone content-team bundle** — `content-team/` — unrelated to the DM
  bot, do not mix them. Seven Claude Code subagents for a content pipeline.
  Not deployed anywhere; install script only. See `content-team/README.md`.

### Infrastructure (live right now)

- **Server**: Google Cloud `e2-micro`, `us-central1-c`, Ubuntu 24.04 Minimal.
  Instance name `podcast-cover-dms`. Free tier — confirm the account has been
  upgraded to paid before **2026-11-15**, or Always Free stops applying and
  the box may be reclaimed. Static IP reserved: **`34.56.254.33`**.
- **HTTPS**: working, via Caddy + `sslip.io` (no owned domain needed).
  Hostname: `34.56.254.33.sslip.io`.
- **Firewall**: `allow-web` rule (tcp:80,443, all instances, no target-tag
  dependency — see Fixed Problems below for why it's untagged).
- **The app is running**: `sudo systemctl status podcast-cover-dms` →
  `active (running)`. `curl https://34.56.254.33.sslip.io/health` → `{"status":"ok"}`.
- **Telegram**: fully wired. Bot created, chat ID found, webhook registered
  and confirmed (`{"ok":true,...,"description":"Webhook was set"}`), a real
  message round-tripped through and appeared in the server log.

  ⚠️ **The original bot token was exposed in a `journalctl` log line and in
  this chat transcript.** The fix that stops it recurring is deployed
  (`app/main.py` silences `httpx`'s request-URL logging — see Fixed Problems).
  **Whether the token was actually rotated at @BotFather is unconfirmed** —
  the last message in this conversation was walking through that rotation.
  **First thing to verify on pickup**: confirm the token in
  `/etc/podcast-cover-dms/env` is the *rotated* one, not the leaked one, and
  that `set_telegram_webhook.py` was re-run afterward so the registered
  webhook matches the current token.

### Fixed problems (so they aren't rediscovered)

Each of these cost real back-and-forth; the fix is already deployed, but the
reasoning is worth knowing if something adjacent breaks:

1. **Ubuntu Minimal lacks `gnupg`/`nano`/`ca-certificates`** → Caddy's install
   needs `gpg` to dearmor its signing key. Added to `setup.sh`'s apt install list.
2. **`gpg --dearmor` prompts "Overwrite?" on a re-run**, hanging a
   non-interactive `sudo` session. Fixed with `--batch --yes`.
3. **GCP's "Allow HTTP/HTTPS traffic" checkboxes tag the instance but don't
   always create the matching firewall rule.** The rule genuinely didn't
   exist — confirmed by listing `VPC network → Firewall`, only
   ssh/rdp/internal/icmp were present. Created `allow-http`/`allow-https`
   manually, tag-scoped, which *still* didn't work — Let's Encrypt's own ACME
   validation was timing out identically to `curl` from the VM itself, which
   ruled out a hairpin-NAT theory and confirmed a genuine external block.
   Deleted those and replaced with **`allow-web`, untagged (applies to all
   instances in the network)**, removing tag-matching as a variable entirely.
   That fixed it — `journalctl -u caddy -f` showed `"certificate obtained
   successfully"` within the same restart.
4. **`sudo git pull` fails with "detected dubious ownership"** on any run
   after the first, because `setup.sh` `chown`s the directory to the `dmbot`
   service user at the end, and root running git in a non-root-owned
   directory is refused by git's ownership check (this is a real git
   security feature, not a bug). Fixed by registering a `git config --global
   --add safe.directory` exception inside `setup.sh` itself, so both manual
   pulls and the script's own re-run/update path are covered, idempotently.
5. **`telegram_setup.py` only checked `./​.env`**, so it failed on the server
   where credentials live at `/etc/podcast-cover-dms/env` instead (by
   design — keeps secrets outside the git-managed directory a redeploy
   replaces). Fixed with auto-detection across both locations, extracted into
   a shared `scripts/_envfile.py` used by both deploy scripts.
6. **`/etc/podcast-cover-dms/env` is `root:dmbot 640` on purpose** — the
   running service can read its own credentials but never write them
   (principle of least privilege). This means any script that *writes* to
   that file (`telegram_setup.py`) must run as **root**, not
   `sudo -u dmbot`. Read-only scripts (`set_telegram_webhook.py`) run fine as
   `dmbot`. The script now fails with an explicit "run as root instead"
   message rather than a raw `PermissionError` traceback.
7. **`set_telegram_webhook.py` read `os.environ` directly**, which is correct
   for the *app* (systemd's `EnvironmentFile=` injects real env vars for that
   process) but wrong for a standalone script nobody has exported variables
   into. Rewritten to use the same `scripts/_envfile.py` module.
8. **Credential leak via `httpx`'s own request logging.** `httpx` logs every
   outgoing request at `INFO`, full URL included. Telegram's Bot API embeds
   the bot token directly in the URL path
   (`api.telegram.org/bot<TOKEN>/method`); the Instagram client (once wired
   up) will do the same via `access_token` as a URL query parameter. Under
   `logging.basicConfig(level=INFO)`, this printed the token in plaintext to
   `journalctl` — which is exactly how the token above got exposed, via a
   routine `journalctl -u podcast-cover-dms -f` session. **Fix deployed**:
   `logging.getLogger("httpx").setLevel(logging.WARNING)` in `app/main.py`.
   Regression test added (`tests/test_webhook_endpoints.py`). This also
   pre-empts the same leak happening to the Instagram access token and any
   Gemini API key passed as a URL param — worth keeping this pattern in mind
   for any *new* HTTP client added later.

---

## Pending — in the order I'd do them

### 1. Confirm the Telegram token rotation (urgent, ~2 minutes)
See the ⚠️ above. Don't skip this — a leaked bot token is a real compromise
vector (someone with it can send messages that appear to come from a trusted
bot, or hijack the webhook to intercept every approval).

### 2. Gemini — needs an API key and a confirmed model id
`LLM_PROVIDER=gemini` is already set as the default in `.env.example`.
Outstanding: `GEMINI_API_KEY` was never filled in (real key from
[aistudio.google.com](https://aistudio.google.com)), and **the exact model
id was never confirmed** — the user asked for "Gemini 3.7 Flash", which
doesn't match any real Gemini model name I'm aware of (possibly confused with
Claude Sonnet 3.7's naming). Currently defaulted to `gemini-2.5-flash` in
`.env.example`. **Check Google's current model list and set the real one** —
a wrong id fails at draft time with a 404, not at startup, so this is easy to
leave silently broken.

Once set: `sudo nano /etc/podcast-cover-dms/env`, fill `GEMINI_API_KEY` and
confirm `GEMINI_MODEL`, `sudo systemctl restart podcast-cover-dms`.

### 3. Instagram — the big remaining piece
Nothing filled in yet. Needed in `/etc/podcast-cover-dms/env`:

- `IG_APP_SECRET` — from the Meta app dashboard (App Settings → Basic)
- `IG_VERIFY_TOKEN` — any string you invent; same value goes into Meta's
  webhook subscription form
- `IG_ACCESS_TOKEN` — **this is the blocker.** Requires the
  `instagram_business_manage_messages` scope (Instagram Login) or
  `instagram_manage_messages` (Facebook Login for Business) — a posting-only
  token does not have this. Getting a token with this scope for real,
  non-tester accounts requires **Meta App Review**, which is days-to-weeks,
  not instant. Start that submission early; it's the actual long pole on this
  whole project, not the code.
- Also confirm **which login flavour** the token is (Instagram Login vs
  Facebook Login for Business) — decides `IG_BASE_URL` and `IG_SEND_NODE` in
  the env file. Ask the user if unclear.
- **Critical, easy to miss**: in the Instagram app itself, **Settings →
  Messages and story replies → Connected tools → Allow access to messages**
  must be switched on, or webhooks never fire even with a correct token.
- While in App Review dev/testing mode, webhooks only fire for accounts with
  a role on the app (you, and any testers you add) — so you *can* test
  end-to-end with your own account today, before Review completes.

Once the token exists: subscribe the Meta webhook to the `messages` field on
the Instagram object, callback URL `https://34.56.254.33.sslip.io/webhooks/instagram`,
verify token = whatever was set above.

### 4. Test against a real DM thread — still never done
This is the one thing that's been true since the very first message of this
whole project: **the actual drafting quality has never been checked against
a real conversation.** Everything built so far is plumbing. Once Instagram
or even just a hand-fed test is possible, the actual test is: does draft
output sound like the user, follow the strategy rules in `prompts/dm-reply.md`
correctly (no pitching in first contact, no re-pitching a soft no, etc.), and
hold up against `examples/*.json` and `scripts/check_examples.py`.

### 5. Nice-to-haves, not blocking
- **Backups off-server.** `deploy/backup.sh` runs nightly to
  `/var/backups/podcast-cover-dms/` but it's on the *same disk* — a lost VM
  loses backups too. Worth copying off-box once there's real lead history
  worth protecting (e.g. to a small GCS bucket, still inside free tier at
  this volume).
- **CI/CD.** Currently every deploy is `sudo git pull && sudo systemctl
  restart podcast-cover-dms` by hand over SSH. A GitHub Action that SSHes in
  and does this on push to the branch would remove the manual step — flagged
  earlier as a good later improvement, not yet built.
- **Upgrade the GCP account to paid** before 2026-11-15 (see Infrastructure
  above) — required to keep Always Free active, does not itself trigger
  charges on an `e2-micro`.

---

## Where things live, for quick reference

| What | Where |
|---|---|
| App code | `app/` |
| Prompt (the actual product) | `prompts/dm-reply.md` |
| Tests | `tests/` — `python3 -m pytest tests -q` |
| Deploy scripts + runbook | `deploy/` |
| Local dev env template | `.env.example` |
| Live server credentials | `/etc/podcast-cover-dms/env` (on the server, not in git) |
| Live server database | `/var/lib/podcast-cover-dms/dms.sqlite3` (on the server, not in git) |
| Content-team bundle (separate product) | `content-team/` |
| Server IP | `34.56.254.33` (static, reserved) |
| Server hostname / webhook base | `https://34.56.254.33.sslip.io` |
| GCP project | `project-a9459707-b1a7-406a-944` |
