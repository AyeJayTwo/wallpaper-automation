# Cron Setup Guide

This guide explains how to set up automatic daily wallpaper generation using cron.

## Quick Setup

1. Make the script executable:
```bash
chmod +x scripts/daily_generate.sh
```

2. Edit your crontab:
```bash
crontab -e
```

3. Add this line (generates at 5:30 AM daily):
```cron
30 5 * * * /Users/ankitjain/Documents/Obsidian/Ankit\ Vault/Wallpaper\ Automation/scripts/daily_generate.sh
```

## Cron Schedule Explained

```
30 5 * * *
│  │ │ │ │
│  │ │ │ └── Day of week (0-7, * = every day)
│  │ │ └──── Month (1-12, * = every month)
│  │ └────── Day of month (1-31, * = every day)
│  └──────── Hour (0-23)
└─────────── Minute (0-59)
```

### Common Schedules

```cron
# 5:30 AM daily
30 5 * * * /path/to/daily_generate.sh

# 6:00 AM daily
0 6 * * * /path/to/daily_generate.sh

# Midnight daily
0 0 * * * /path/to/daily_generate.sh

# Every hour (for testing)
0 * * * * /path/to/daily_generate.sh
```

## Verifying Setup

### Check cron is running
```bash
crontab -l
```

### Check logs
```bash
tail -f logs/generate.log
```

### Test manually
```bash
./scripts/daily_generate.sh
```

## Troubleshooting

### Cron not running?

1. **Check cron service** (macOS):
   ```bash
   sudo launchctl list | grep cron
   ```

2. **Grant Full Disk Access** to cron:
   - System Preferences → Security & Privacy → Privacy → Full Disk Access
   - Add `/usr/sbin/cron`

3. **Check mail for errors**:
   ```bash
   mail
   ```

### Python not found?

Use full path to Python in the script:
```bash
/usr/local/bin/python3 generate.py
```

Or specify PATH in crontab:
```cron
PATH=/usr/local/bin:/usr/bin:/bin
30 5 * * * /path/to/daily_generate.sh
```

### Permission denied?

```bash
chmod +x scripts/daily_generate.sh
```

## With iCloud Delivery

To automatically deliver to iCloud for Shortcuts, uncomment the delivery lines in `daily_generate.sh`:

```bash
# Deliver to iCloud
log "Delivering to iCloud..."
if python3 scripts/deliver_to_shortcuts.py --icloud >> "$LOG_FILE" 2>&1; then
    log "Delivered to iCloud successfully"
else
    log "WARNING: Failed to deliver to iCloud"
fi
```

## Alternative: launchd (macOS native)

If you prefer launchd over cron, create `~/Library/LaunchAgents/com.wallpaper.daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wallpaper.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/ankitjain/Documents/Obsidian/Ankit Vault/Wallpaper Automation/scripts/daily_generate.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>5</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/ankitjain/Documents/Obsidian/Ankit Vault/Wallpaper Automation/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/ankitjain/Documents/Obsidian/Ankit Vault/Wallpaper Automation/logs/launchd.error.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.wallpaper.daily.plist
```
