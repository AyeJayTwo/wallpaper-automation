# Wallpaper Automation

## Quick Commands

```bash
# Generate today's wallpaper (iPhone)
python3 generate.py

# Generate e-ink wallpaper for specific date
python3 generate.py --date 2026-02-05 --eink

# Download latest Readwise Reader articles as EPUBs (no device upload)
python3 -m src.reader --max 10

# Upload to CrossPoint e-reader (auto-detects network)
~/.claude/skills/crosspoint-wallpaper/scripts/upload_wallpaper.sh [DATE] [IP]
```

## CrossPoint E-Reader Integration

### Device: Xteink X4 with CrossPoint firmware

**Network IPs:**
- JainCubed (home): `192.168.1.69`
- Swiftly-Corp (work): `10.1.16.252`

**Connection quirks:**
- Device has weak WiFi - use 300s timeout for uploads
- SSID detection unreliable on macOS - detect network by Mac's IP prefix instead
- Device may not respond to ping/status checks even when online
- Check ARP table (`arp -a | grep <IP>`) to confirm device presence
- Must include `-H "Expect:"` header in curl uploads

**Upload requirements:**
- Device must be on File Upload screen (web server only runs in this mode)
- Sleep screen: 480x800 pixels, uncompressed BMP, 24-bit color
- Upload as `sleep.bmp` to root directory
- Set Sleep Screen to "Custom" in device settings

**Synology watcher (`scripts/watch_and_upload.py`):**
When the Xteink appears on the LAN File Upload screen, the watcher uploads
today's sleep wallpaper **and** any new Reader articles (as `.epub`) that have
not been synced yet. Requires `READWISE_TOKEN` in `.env`.

## Output Paths

- iPhone wallpapers: `output/iphone/wallpaper_YYYY-MM-DD.png`
- E-ink wallpapers: `output/eink/eink_YYYY-MM-DD.bmp`
- Reader articles: `output/reader/*.epub`
