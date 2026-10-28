#!/usr/bin/env bash
set -euo pipefail

repo_root="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
canonical_root="$repo_root/.agents/skills"

if [[ ! -d "$canonical_root" ]]; then
  echo "missing canonical skill root: .agents/skills" >&2
  exit 2
fi
if [[ -d "$repo_root/.codex/skills" || -d "$repo_root/tools/codex/skills" ]]; then
  echo "duplicate repository skill root detected" >&2
  exit 2
fi
for skill in cxet-workflow cxet-audit-plan; do
  if [[ ! -f "$canonical_root/$skill/SKILL.md" ]]; then
    echo "missing canonical workflow skill: $skill" >&2
    exit 2
  fi
done

find "$canonical_root" -mindepth 2 -maxdepth 2 -name SKILL.md -print | sort
