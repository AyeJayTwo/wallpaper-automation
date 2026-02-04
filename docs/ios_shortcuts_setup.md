# iOS Shortcuts Setup Guide

This guide explains how to set up automatic wallpaper updates on your iPhone using the Shortcuts app.

## Overview

The automation works in two parts:
1. **Mac**: Generates wallpaper daily and syncs to iCloud
2. **iPhone**: Shortcuts automation sets the wallpaper

## Part 1: Mac Setup

### Deliver to iCloud

After generating a wallpaper, run the delivery script:

```bash
# Generate today's wallpaper
python generate.py

# Deliver to iCloud Shortcuts folder
python scripts/deliver_to_shortcuts.py --icloud
```

The wallpaper will sync to your iPhone via iCloud.

### Automated Delivery

Add delivery to your cron job (see cron_setup.md):

```bash
cd /path/to/wallpaper-automation && python generate.py && python scripts/deliver_to_shortcuts.py --icloud
```

## Part 2: iPhone Shortcut Setup

### Create the Shortcut

1. Open **Shortcuts** app on iPhone
2. Tap **+** to create new shortcut
3. Add these actions:

#### Action 1: Get File
- Action: **Get File**
- Service: **iCloud Drive**
- Path: `Shortcuts/Wallpapers/calendar_wallpaper.png`

#### Action 2: Set Wallpaper
- Action: **Set Wallpaper**
- Input: File from previous action
- Screen: **Lock Screen** (or Both)

4. Name the shortcut: "Set Calendar Wallpaper"

### Set Up Automation

1. Go to **Shortcuts** → **Automation** tab
2. Tap **+** → **Create Personal Automation**
3. Choose trigger: **Time of Day**
   - Time: 6:00 AM (or your preferred time)
   - Repeat: Daily
4. Add action: **Run Shortcut** → "Set Calendar Wallpaper"
5. Turn OFF "Ask Before Running"
6. Tap **Done**

## Alternative: Direct File Access

If you prefer not to use iCloud, you can:

1. Run the Mac as a web server serving the wallpaper
2. Use Shortcuts' **Get Contents of URL** action
3. Set the wallpaper from the downloaded image

## Troubleshooting

### Wallpaper not updating?
- Check iCloud sync status on both devices
- Verify the file exists in iCloud Drive → Shortcuts → Wallpapers
- Check Shortcuts automation is enabled

### File not found?
- Ensure the delivery script ran successfully
- Check the iCloud path matches the Shortcut's Get File path

### Automation not running?
- Go to Settings → Shortcuts → Advanced
- Enable "Allow Running Scripts"
- Check automation hasn't been paused
