#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$repo_root/.venv/bin/python"

if [ ! -x "$python_bin" ]; then
  echo "Expected .venv/bin/python. Run the setup steps in README.md first." >&2
  exit 1
fi

three_module="$repo_root/visualizer/node_modules/three/build/three.module.js"
if [ ! -f "$three_module" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to install the Everett visualizer dependency." >&2
    exit 1
  fi
  echo "Installing the Everett visualizer dependency..." >&2
  npm install --prefix "$repo_root/visualizer" >&2
fi

"$python_bin" -c 'from server.showcase import launch_showcase; print(launch_showcase())'
