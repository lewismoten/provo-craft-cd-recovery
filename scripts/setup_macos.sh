#!/usr/bin/env bash
# Install the macOS command-line dependencies used by recover_cd.py.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This setup script targets macOS/Homebrew." >&2
  exit 2
fi

if ! command -v brew >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Homebrew is required but is not installed.
Install Homebrew first from https://brew.sh/, then run this script again.
EOF
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
brew bundle --file "$repo_root/Brewfile"

echo "Dependencies installed. Verify with: python3 scripts/recover_cd.py --help"
