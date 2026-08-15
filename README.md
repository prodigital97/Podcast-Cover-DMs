# Podcast Cover — DM drafts

Instagram DMs arrive, Claude drafts three replies in Pronoy's voice, the drafts land in
Telegram, and nothing reaches Instagram until a button is tapped.

```
Instagram DM ──webhook──▶ service ──▶ builds/updates the lead from the Graph API
                                 └──▶ Claude drafts 3 replies
                                        │
                          Telegram card ▼   [Send 1][Send 2][Send 3]
                                            [Edit][Redraft][Skip]
                                        │
Instagram reply ◀──── approved text ────┘
```

The lead profile — handle, follower count, bio, how they type, pipeline stage, what
they need — is built and maintained automatically from the API and from the
conversation. There are no profiles to fill in by hand.

## Files

| Path | What it is |
| --- | --- |
| `prompts/dm-reply.md` | The system prompt. The strategy rules live here. |
| `app/main.py` | FastAPI service — the Instagram and Telegram webhooks. |
| `app/approvals.py` | The flow: inbound DM → drafts → card → approved reply. |
| `app/drafting.py` | Builds the prompt; infers how a lead writes from how they've written. |
| `app/providers.py` | The model backend — Claude or Gemini, chosen by `LLM_PROVIDER`. |
| `app/instagram.py` | Signature checks, profile lookup, sending, the 24h window. |
| `app/telegram.py` | The approval card and its buttons. |
| `app/db.py` | SQLite: leads, message history, pending approvals. |
| `leads/`, `examples/`, `scripts/` | The offline side: lead format, worked examples, CLI. |

## Running it

```sh
pip install -r requirements.txt
cp .env.example .env        # then fill it in — every field is commented
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Point Meta's webhook at `https://<host>/webhooks/instagram` (subscribe to `messages`
on the Instagram object) and register the Telegram side:

```sh
python3 scripts/set_telegram_webhook.py https://<host>
```

It needs a public HTTPS host — Meta and Telegram both push to you. A small VPS or a
Railway/Fly instance is enough; the process is not CPU-bound and the database is a
single SQLite file.

### What you'll need from Meta

The posting token is not sufficient. Messaging needs `instagram_business_manage_messages`
(Instagram Login) or `instagram_manage_messages` (Facebook Login for Business), which
means adding the scope and re-authorising — and in the Instagram app itself,
**Settings → Messages → Connected tools → Allow access to messages** has to be on, or
webhooks never fire.

Reading a sender's *bio* is a separate thing again: it comes from `business_discovery`,
which needs a Facebook Login token with `instagram_basic` and only works for
professional accounts. Set `IG_USER_ID` and `IG_DISCOVERY_TOKEN` if you have one.
Without it, leads are built from the messaging profile alone and `bio` stays unknown —
the drafter is told "unknown" rather than being left to invent something.

## Choosing the model

`LLM_PROVIDER=anthropic` or `LLM_PROVIDER=gemini`. Both use native structured
outputs, so the drafts come back schema-valid or the call fails — there is no
JSON-repair path to go wrong. Only the selected provider's API key is needed.

Set `GEMINI_MODEL` to the exact id you want. An unknown id fails at draft time
with a 404 rather than at startup, so check it against Google's current model
list before you rely on it.

Whichever you pick, judge it on real threads rather than on the spec sheet.
This is a voice-matching and judgement task — the failure mode of a weaker model
here is not malformed output, it is drafts that are fluent and slightly generic,
which is exactly the thing the strategy rules exist to prevent.

## The 24-hour window

Instagram allows a reply within 24 hours of the person's last message. Past that, a
send fails with a clear error rather than silently dropping. The `HUMAN_AGENT` tag
extends it to 7 days, but only once Meta approves the `human_agent` permission for
your app — set `IG_USE_HUMAN_AGENT_TAG=1` after that, not before.

This is why the service only ever *replies*. It has no outbound path, by design:
automated cold DMs are what gets accounts actioned, and the account is the asset.

## Approving

Each card shows who they are, what they sent, the model's read of it, and three drafts.

- **Send 1/2/3** — delivers that draft as-is.
- **Edit** — reply to the bot with your own text; that goes instead.
- **Redraft** — throws the three away and asks for a visibly different angle.
- **Skip** — closes the card and sends nothing.

A card can only resolve once. If a send fails, the card stays open and the failure is
reported in the thread rather than being swallowed.

## The stages

- **first_contact** — one or two exchanges. No pitch, ever. Close on a question.
- **building** — talking, but they have not asked for anything. Still no pitch.
- **green_light** — they asked what you do, mentioned needing help, raised
  collaborating, or asked what it costs. Pitch a free sample built from material
  they already have.
- **soft_no** — "we have someone", "not right now", "I'll keep you in mind". Close
  warmly. The only permitted move is offering to send something with zero obligation.
- **hard_no** — close and stop.
- **active_client** — they are paying. Answer as their supplier, not as a lead chaser.

The model returns the stage it reads from each new message, and the lead's status
follows it. It also reports what changed in `needs` / `offered` / `price` /
`commitments`, so the pipeline maintains itself.

## The rules that get broken most

**Length.** A one-line message gets one or two lines back. The pitch drafts are the
ones that creep, because a pitch feels like it needs explaining. It does not — see
`examples/02`, where the whole offer fits in thirty words.

**Re-pitching a soft no.** "Might come back to you later" is a close, not an
invitation to make the case again. `examples/04` is the shape: acknowledge, wish them
well, leave the door open once and stop.

## Working offline

Render a prompt from a lead file without running the service:

```sh
python3 scripts/render_prompt.py leads/example-lead.json
```

## Checking changes

```sh
python3 -m pytest tests -q          # 47 tests, no credentials needed
python3 scripts/check_examples.py   # the worked examples against the strategy rules
```

The tests stub Instagram and Telegram, so the whole approval flow — including the
duplicate-webhook, failed-send, and redraft paths — runs offline. What they cannot
check is whether a draft actually sounds like Pronoy; read those.
