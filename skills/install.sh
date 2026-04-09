#!/usr/bin/env bash
# install.sh — Register the Franken-Stream OpenClaw skill
#
# Usage:
#   bash skills/install.sh [--openclaw-dir <path>]
#
# Options:
#   --openclaw-dir   Path to the OpenClaw skills directory.
#                    Defaults to ~/.openclaw/skills
#
# The script:
#   1. Checks for required binaries (python3, mpv)
#   2. Installs Python dependencies
#   3. Starts the Franken-Stream server (if not already running)
#   4. Writes the skill registration entry to the OpenClaw config

set -euo pipefail

# ---- defaults ---------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
SKILLS_DIR="$OPENCLAW_DIR/skills/franken_stream"
SERVER_PORT="${FRANKEN_STREAM_PORT:-3001}"
PYTHON="${PYTHON:-python3}"

# ---- parse args -------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --openclaw-dir) OPENCLAW_DIR="$2"; shift 2 ;;
        --port)         SERVER_PORT="$2";  shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# ---- helpers ----------------------------------------------------------------
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

check_bin() {
    command -v "$1" &>/dev/null || die "'$1' not found. Please install it."
}

# ---- preflight checks -------------------------------------------------------
info "Checking prerequisites…"
check_bin "$PYTHON"
check_bin "mpv"

# ---- install Python deps ----------------------------------------------------
info "Installing Python dependencies…"
"$PYTHON" -m pip install --quiet -r "$REPO_ROOT/requirements.txt"

# ---- optional: start the server --------------------------------------------
if curl -sf "http://localhost:$SERVER_PORT/health" &>/dev/null; then
    info "Franken-Stream server already running on port $SERVER_PORT."
else
    info "Starting Franken-Stream server in the background…"
    if command -v cargo &>/dev/null && [ -f "$REPO_ROOT/Cargo.toml" ]; then
        (cd "$REPO_ROOT" && BIND_ADDR="0.0.0.0:$SERVER_PORT" cargo run -p server &>/tmp/franken-stream-server.log &)
        info "Server starting (logs: /tmp/franken-stream-server.log)."
    else
        warn "cargo not found — skipping Rust server startup."
        warn "Start the server manually: cd $REPO_ROOT && cargo run -p server"
    fi
fi

# ---- write skill manifest ---------------------------------------------------
info "Installing skill manifest to $SKILLS_DIR…"
mkdir -p "$SKILLS_DIR"

cp "$REPO_ROOT/SKILL.md" "$SKILLS_DIR/SKILL.md"

cat > "$SKILLS_DIR/skill.json" <<EOF
{
  "name": "franken_stream",
  "version": "1.0.0",
  "description": "Search and stream movies, TV shows, internet radio, podcasts, audiobooks, live TV channels, and sports scores.",
  "endpoint": "http://localhost:${SERVER_PORT}/openclaw",
  "method": "POST",
  "intent_schema": {
    "intent": "string",
    "params": "object"
  },
  "env": {
    "SPORTS_API_KEY": ""
  }
}
EOF

# ---- write OpenClaw config entry -------------------------------------------
OPENCLAW_CONFIG="$OPENCLAW_DIR/config.json"

if [ ! -f "$OPENCLAW_CONFIG" ]; then
    mkdir -p "$OPENCLAW_DIR"
    echo '{"skills": {"entries": {}}}' > "$OPENCLAW_CONFIG"
fi

# Use Python to safely merge the skill entry into the existing config JSON
"$PYTHON" - "$OPENCLAW_CONFIG" "$SERVER_PORT" <<'PYEOF'
import json, sys

config_path = sys.argv[1]
port        = sys.argv[2]

with open(config_path) as fh:
    config = json.load(fh)

config.setdefault("skills", {}).setdefault("entries", {})["franken_stream"] = {
    "enabled":  True,
    "endpoint": f"http://localhost:{port}/openclaw",
    "env": {
        "SPORTS_API_KEY": ""
    }
}

with open(config_path, "w") as fh:
    json.dump(config, fh, indent=2)

print(f"Wrote skill entry to {config_path}")
PYEOF

# ---- done -------------------------------------------------------------------
echo ""
echo "============================================================"
echo " Franken-Stream OpenClaw skill installed successfully!"
echo "============================================================"
echo ""
echo " Endpoint : http://localhost:$SERVER_PORT/openclaw"
echo " Manifest : $SKILLS_DIR/SKILL.md"
echo " Config   : $OPENCLAW_CONFIG"
echo ""
echo " Test with:"
echo "   curl -s -X POST http://localhost:$SERVER_PORT/openclaw \\"
echo '     -H "Content-Type: application/json" \'
echo '     -d '"'"'{"intent":"stream","params":{"title":"Inception"}}'"'"
echo ""
echo " Or via Python:"
echo "   python -m franken_stream.openclaw_skill 'Stream Inception'"
echo "   python -m franken_stream.openclaw_skill 'Play some jazz radio'"
echo "   python -m franken_stream.openclaw_skill 'Watch Breaking Bad S5E14'"
echo ""
echo " If you set SPORTS_API_KEY in $OPENCLAW_CONFIG,"
echo " live scores will also be available."
echo "============================================================"
