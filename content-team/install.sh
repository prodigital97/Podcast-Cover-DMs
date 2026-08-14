#!/usr/bin/env bash
# Install the content team into a project.
#
#     ./install.sh ~/path/to/your/content-project
#
# Copies the seven employees and the two commands into the target project's
# .claude/ directory, and seeds tasks/ and brand/ if they are not already there.
# Existing files are never overwritten — your filled-in style and calendar
# survive a re-run.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:-}"

if [[ -z "$target" ]]; then
    echo "usage: $0 <path-to-project>" >&2
    exit 2
fi
if [[ ! -d "$target" ]]; then
    echo "no such directory: $target" >&2
    exit 1
fi

target="$(cd "$target" && pwd)"
if [[ "$target" == "$here"* ]]; then
    echo "refusing to install into the bundle itself" >&2
    exit 1
fi

mkdir -p "$target/.claude/agents" "$target/.claude/commands" \
         "$target/tasks/scripts" "$target/tasks/checklists" "$target/brand"

# Agents and commands are the product — always refresh them.
cp "$here"/agents/*.md "$target/.claude/agents/"
cp "$here"/commands/*.md "$target/.claude/commands/"
echo "installed 7 employees and 2 commands"

# Working files carry your content — seed once, then leave alone.
seeded=0
for file in tasks/calendar.md tasks/briefs.md tasks/metrics.md brand/style.md brand/voice.md; do
    if [[ -e "$target/$file" ]]; then
        echo "  kept existing $file"
    else
        cp "$here/$file" "$target/$file"
        seeded=$((seeded + 1))
    fi
done
echo "seeded $seeded working file(s)"

cat <<'NEXT'

Next:
  1. Fill the TODOs in brand/style.md — the Designer refuses to work without them.
  2. Paste 5-10 of your real captions into brand/voice.md.
  3. Restart Claude Code in the project, then run /content-day.
NEXT
