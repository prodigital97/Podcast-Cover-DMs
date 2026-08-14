# 7 AI employees, one creator

A content team as Claude Code subagents. Seven specialists, each with one job,
handing off in order through two shared files.

Nothing here is connected to the DM bot in this repo — separate files, separate
install, no shared code.

## Install

```sh
./install.sh ~/path/to/your/content-project
```

That copies the seven employees into `.claude/agents/` and the two commands into
`.claude/commands/`, then seeds `tasks/` and `brand/` if they aren't there
already. Re-running refreshes the employees and leaves your filled-in calendar,
briefs and style file untouched.

Restart Claude Code in that project and the team is hired.

## The team

| Employee | One job | Tools it gets |
| --- | --- | --- |
| researcher | Find what to make before you ask | web search, files |
| hook-writer | Own the first two seconds | files |
| script-writer | Turn the pick into the actual post | files |
| designer | Make it look like a brand, not a bot | files, bash |
| analyst | Say what actually worked | files |
| manager | Run the calendar so nothing collides | files |
| publisher | Prep every post to ship on time | files |

Each employee's tool list is deliberately narrow. The hook-writer cannot search
the web, so it cannot quietly invent a number instead of using the brief's. The
analyst cannot browse, so it cannot go looking for a metric it wasn't given.
The one-job rule only holds if the tools hold it.

## Running a day

```
/content-day
/content-day push the pricing angle          # optional focus
/review-day
```

Employees run in sequence, not in parallel — each one needs the last one's
output. If one hits a blocker it stops and says so rather than working around
it, which is the behaviour you want: a carousel built on an unfilled style file
is worse than no carousel.

## The files the team shares

```
tasks/calendar.md    what ships when — manager writes, publisher logs
tasks/briefs.md      the openings — researcher and analyst write, everyone reads
tasks/metrics.md     the only place the analyst may read numbers from
tasks/scripts/       finished scripts, one file per piece
tasks/checklists/    what the publisher hands you at posting time
brand/style.md       locked design tokens — the designer refuses without these
brand/voice.md       your real captions — how the script-writer learns your voice
```

Each file carries its own format at the top, so employees read the shape from
the file they're writing into rather than each inventing one. That's what makes
the handoffs survive a restart.

## Two things to fill in before the first run

**`brand/style.md`** ships full of `TODO`s and the Designer is told to refuse
briefs that would break the locked style. Unfilled tokens are exactly why AI
design looks like AI design: the model picks something reasonable and *different*
every time, so nothing accumulates into a brand. Fill the palette, type stack
and grid once.

**`brand/voice.md`** wants five to ten of your real captions, pasted unedited.
The Script Writer is told to "study past captions first" — this is the only
place it can find them. Descriptions of your voice do far less work than
examples of it.

## What this does and doesn't do

**The Publisher never posts.** It prepares the file, the caption, the slot and
the checklist, and you hit post. That stays true no matter how good the team
gets — it's the same reason the DM bot drafts but never sends.

**The Designer needs a real export path.** It writes each slide as a
self-contained HTML file at the exact pixel size and shells out to a capture
script to render it. Without one it produces specs and markup, not
ready-to-post PNGs. If you want, I can wire the capture step up — Chromium is
the usual answer and it's already how most of these pipelines work.

**The Analyst cannot see your numbers.** Nothing here connects to Instagram
Insights. Paste each week's export into `tasks/metrics.md` before review day; if
a week is missing the Analyst reports it unread rather than guessing. That
refusal is deliberate — an invented retention figure is worse than a blank one,
because it feeds the next week's briefs.

## Checking your edits

```sh
python3 check_agents.py
```

Catches what silently stops an employee being hired: broken frontmatter, a
`name` that no longer matches its filename, a duplicate name, an empty body.
