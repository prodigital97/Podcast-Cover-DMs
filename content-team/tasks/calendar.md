# Calendar

The Manager owns the schedule rows. The Publisher appends to the shipped log.
No other employee edits this file.

## Format

Schedule rows are `| date | slot | format | keyword | brief | status |`

- **date** — YYYY-MM-DD
- **slot** — the local posting time, e.g. `19:30`
- **format** — reel / carousel / single / story
- **keyword** — the one keyword this post arms. Two posts may not share a
  keyword inside a rolling 14 days.
- **brief** — the brief id from tasks/briefs.md, e.g. `B-014`. A row with no
  brief id is not assignable.
- **status** — planned / in-progress / ready / shipped / dropped

## Schedule

| date | slot | format | keyword | brief | status |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## Shipped log

Appended by the Publisher only after the human confirms the post is live.

| shipped at | date | format | brief | link |
| --- | --- | --- | --- | --- |
| | | | | |
