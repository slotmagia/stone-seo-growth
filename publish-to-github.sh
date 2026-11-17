#!/usr/bin/env bash
# Run from the extracted Stone Growth OS project directory.
# Requires: git, GitHub account authenticated for HTTPS push.
set -euo pipefail

REMOTE_URL="${1:-https://github.com/slotmagia/stone-seo-growth.git}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
  echo 'Error: git is not installed.' >&2
  exit 1
fi
if [[ -d .git ]]; then
  echo 'Error: local .git already exists; inspect the repository manually to avoid overwriting history.' >&2
  exit 1
fi
if [[ ! -f pyproject.toml || ! -d app || ! -d docs ]]; then
  echo 'Error: expected Stone Growth OS project files are missing.' >&2
  exit 1
fi
if ! remote_refs="$(git ls-remote "$REMOTE_URL" 2>/dev/null)"; then
  echo 'Error: cannot read remote. Check network access and your GitHub repository permissions.' >&2
  exit 1
fi
if [[ -n "$remote_refs" ]]; then
  echo 'Error: remote has commits or refs. To avoid overwriting work, this bootstrap script will not push.' >&2
  exit 1
fi

git init -b main
git add .
git commit -m 'feat: initialize Stone Growth OS SEO/GEO MVP v0.1.0'
git remote add origin "$REMOTE_URL"
git push -u origin main

echo "Published: $REMOTE_URL (main)"
