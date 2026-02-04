#!/bin/bash
# Daily wallpaper generation script for cron
# This script generates the wallpaper and optionally delivers to iCloud

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/generate.log"

# Ensure log directory exists
mkdir -p "$PROJECT_DIR/logs"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "Starting daily wallpaper generation"

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Generate wallpaper
log "Running generate.py..."
if python3 generate.py >> "$LOG_FILE" 2>&1; then
    log "Wallpaper generated successfully"
else
    log "ERROR: Failed to generate wallpaper"
    exit 1
fi

# Deliver to iCloud (optional - uncomment if using)
# log "Delivering to iCloud..."
# if python3 scripts/deliver_to_shortcuts.py --icloud >> "$LOG_FILE" 2>&1; then
#     log "Delivered to iCloud successfully"
# else
#     log "WARNING: Failed to deliver to iCloud"
# fi

log "Daily generation complete"
