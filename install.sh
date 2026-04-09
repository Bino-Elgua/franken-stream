#!/usr/bin/env bash
# franken-stream one-click installer
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing franken-stream..."
python3 -m pip install -e "$REPO_DIR" --quiet

# Detect where pip puts scripts
SCRIPT_DIR="$(python3 -c "import sysconfig; print(sysconfig.get_path('scripts'))")"

# Check if already on PATH
if ! command -v franken-stream &>/dev/null; then
    SHELL_RC=""
    case "$SHELL" in
        */zsh)  SHELL_RC="$HOME/.zshrc" ;;
        */bash) SHELL_RC="$HOME/.bashrc" ;;
        *)      SHELL_RC="$HOME/.profile" ;;
    esac

    echo ""
    echo "==> Adding $SCRIPT_DIR to PATH in $SHELL_RC"
    echo "" >> "$SHELL_RC"
    echo "# franken-stream" >> "$SHELL_RC"
    echo "export PATH=\"$SCRIPT_DIR:\$PATH\"" >> "$SHELL_RC"
    export PATH="$SCRIPT_DIR:$PATH"
fi

echo ""
echo "==> Seeding local providers (offline-safe)..."
python3 -m franken_stream.main update 2>/dev/null || true

echo ""
echo "==> Installation complete!"
echo ""
echo "  Run now:  franken-stream watch \"The Matrix\""
echo "  TV shows: franken-stream tv \"Breaking Bad\" -s 1 -e 5"
echo "  Web UI:   franken-stream web"
echo "  Help:     franken-stream --help"
echo ""
echo "  If 'franken-stream' is not found, reload your shell:"
echo "    source $SHELL_RC"
