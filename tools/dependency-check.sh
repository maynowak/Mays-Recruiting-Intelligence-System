#!/bin/bash
#
# Dependency & Contract Change Checker CLI
#
# Usage:
#   ./tools/dependency-check.sh
#   ./tools/dependency-check.sh --format json
#   ./tools/dependency-check.sh --changed-only
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required but not found" >&2
    exit 3
fi

# Run the Python checker
exec python3 "$SCRIPT_DIR/dependency_check.py" "$@"