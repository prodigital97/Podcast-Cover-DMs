# Podcast Cover — DM reply drafts

The prompt Pronoy uses to draft Instagram DM replies for Podcast Cover, plus the
lead format it reads and worked examples of what good output looks like in four
different worlds.

## Files

| Path | What it is |
| --- | --- |
| `prompts/dm-reply.md` | The system prompt. Everything downstream fills its placeholders. |
| `leads/_schema.json` | Every field the prompt expects, with a note on what belongs in it. |
| `leads/example-lead.json` | A filled lead, ready to render. |
| `scripts/render_prompt.py` | Fills the prompt from a lead file and prints it. |
| `scripts/check_examples.py` | Checks the examples against the rules that can be checked in code. |
| `examples/*.json` | Lead plus expected output, one per stage. |

## Using it

```sh
python3 scripts/render_prompt.py leads/example-lead.json | pbcopy
```

Paste into the model, paste the JSON it returns back into the thread of your
choice. Missing fields render as `unknown` and warn on stderr — that is deliberate,
because a blank is safer than an invented follower count the reply then references.

Before drafting, fill `full_thread` and `incoming_message` honestly. Most bad drafts
come from a thread that was summarised rather than pasted.

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

`stage` in the output should match `status` in the lead unless the new message
moved them, which is the whole point of reading it — the checker flags a mismatch
so you notice you moved someone rather than doing it silently.

## The rules that get broken most

Two of them, consistently:

**Length.** A one-line message gets one or two lines back. The pitch drafts are the
ones that creep, because a pitch feels like it needs explaining. It does not — see
`examples/02`, where the whole offer fits in thirty words.

**Re-pitching a soft no.** "Might come back to you later" is a close, not an
invitation to make the case again. `examples/04` is the shape: acknowledge, wish
them well, leave the door open once and stop.

Everything else — their vocabulary rather than podcast-marketing vocabulary, no
price first, no emoji unless they used one — tends to hold on its own.

## Checking changes

```sh
python3 scripts/check_examples.py
```

It reads `leads/_schema.json`, so adding a field there makes every example fail
until it is filled in. Tone, specificity and whether a reply actually sounds like
Pronoy are not checkable — read the drafts.
