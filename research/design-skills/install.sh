#!/usr/bin/env bash
# Install the vendored design skill packs where opencode reads them.
# Project-level (this repo): .opencode/skills/<pack>/<skill>/SKILL.md
# Global (all projects):     ~/.config/opencode/skills/
# Usage: ./install.sh [--global]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$here/../.." && pwd)"
if [ "${1:-}" = "--global" ]; then
  dest="$HOME/.config/opencode/skills"
else
  dest="$repo_root/.opencode/skills"
fi
mkdir -p "$dest"
for pack in ui-skills ponytail superpowers pstack; do
  for skill_dir in "$here/$pack"/*/; do
    [ -f "$skill_dir/SKILL.md" ] || continue
    name="$(basename "$skill_dir")"
    rm -rf "$dest/$name"
    cp -r "$skill_dir" "$dest/$name"
  done
done
echo "installed $(ls "$dest" | wc -l) skills into $dest"
