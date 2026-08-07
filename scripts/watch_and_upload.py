#!/usr/bin/env python3
"""
Xteink wallpaper watcher for Synology NAS.

Polls the CrossPoint device on the local network.  When it appears (i.e. you
connect the Xteink to home WiFi on the File Upload screen):
  1. Generates today's e-ink BMP (fresh Todoist tasks + Readwise quote).
  2. Uploads it as sleep.bmp via the CrossPoint HTTP endpoint.
  3. Writes a per-day lockfile so the same wallpaper isn't uploaded again
     until tomorrow.

Usage (normally run via Docker):
    python -u scripts/watch_and_upload.py

Environment variables (set via .env / docker-compose):
    DEVICE_IP            IP of the CrossPoint device (default: 10.0.0.164)
    TZ                   Container timezone for date calculations (default: UTC)
    POLL_INTERVAL        Seconds between status checks (default: 20)
    UPLOAD_TIMEOUT       Max seconds for the curl upload (default: 300)
    MAX_RETRIES          Upload retry attempts before backing off (default: 3)
    TELEGRAM_BOT_TOKEN   Optional — Telegram bot token from @BotFather
    TELEGRAM_CHAT_ID     Optional — chat ID to notify on successful upload
"""

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEVICE_IP = os.environ.get("DEVICE_IP", "10.0.0.164")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "20"))
UPLOAD_TIMEOUT = int(os.environ.get("UPLOAD_TIMEOUT", "300"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

APP_DIR = Path(__file__).parent.parent
OUTPUT_DIR = APP_DIR / "output" / "eink"
STATE_DIR = APP_DIR / "state"

STATUS_URL = f"http://{DEVICE_IP}/api/status"
UPLOAD_URL = f"http://{DEVICE_IP}/upload"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("watcher")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def today_str() -> str:
    """Return today's date as YYYY-MM-DD in the local timezone."""
    return datetime.now().strftime("%Y-%m-%d")


def lockfile_path(date: str) -> Path:
    return STATE_DIR / f"uploaded_{date}"


def already_uploaded(date: str) -> bool:
    return lockfile_path(date).exists()


def write_lockfile(date: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lockfile_path(date).write_text(
        f"Uploaded at {datetime.now().isoformat()}\n"
    )


def device_online() -> bool:
    """
    Return True if the CrossPoint device responds on its status endpoint.
    Uses a short timeout — flaky WiFi is expected; failures are normal.
    """
    try:
        req = urllib.request.Request(STATUS_URL, headers={"User-Agent": "xteink-watcher/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            # CrossPoint returns {"device":"X4",...}; any non-empty JSON is fine
            return bool(body.strip())
    except Exception:
        return False


def generate_eink(date: str) -> Path:
    """
    Run generate.py --eink for the given date.
    Returns the path to the generated BMP.
    Raises subprocess.CalledProcessError on failure.
    """
    output_path = OUTPUT_DIR / f"eink_{date}.bmp"
    log.info("Generating e-ink wallpaper for %s ...", date)
    subprocess.run(
        [sys.executable, str(APP_DIR / "generate.py"), "--eink", "--date", date, "-v"],
        check=True,
        cwd=str(APP_DIR),
    )
    if not output_path.exists():
        raise FileNotFoundError(f"Expected output not found: {output_path}")
    log.info("Generated: %s", output_path)
    return output_path


def upload(bmp_path: Path) -> bool:
    """
    Upload bmp_path as sleep.bmp to the CrossPoint device using curl.

    Uses the same flags as the known-good upload_wallpaper.sh:
      -H "Expect:"          prevents 100-continue issues with the device
      --max-time 300        device has weak WiFi; uploads can be very slow
      -F "file=@..;filename=sleep.bmp"

    Returns True on success, False on failure.
    Curl exit codes 28 (timeout) and 56 (recv failure) are treated as
    retryable network errors, not permanent failures.
    """
    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--max-time", str(UPLOAD_TIMEOUT),
        "-H", "Expect:",
        "-X", "POST",
        "-F", f"file=@{bmp_path};filename=sleep.bmp",
        UPLOAD_URL,
    ]
    log.info("Uploading %s to %s ...", bmp_path.name, UPLOAD_URL)
    result = subprocess.run(cmd, capture_output=True, text=True)
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode == 0 and "successfully" in stdout.lower():
        log.info("Upload successful: %s", stdout)
        return True

    if result.returncode in (28, 56):
        log.warning("Upload network error (curl %d): %s", result.returncode, stderr)
        return False

    log.warning(
        "Upload failed (curl %d). stdout=%r stderr=%r",
        result.returncode, stdout, stderr,
    )
    return False


def run_upload_with_retries(bmp_path: Path) -> bool:
    """
    Attempt the upload up to MAX_RETRIES times with exponential backoff.
    Returns True if any attempt succeeds.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        if upload(bmp_path):
            return True
        if attempt < MAX_RETRIES:
            wait = 2 ** attempt  # 2s, 4s, 8s
            log.info("Retry %d/%d in %ds ...", attempt, MAX_RETRIES, wait)
            time.sleep(wait)
    log.error("Upload failed after %d attempts, will retry on next device detection.", MAX_RETRIES)
    return False


def notify_telegram(date: str) -> None:
    """
    Send a Telegram message on successful upload.

    No-op if TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is unset.
    Failures are logged but never raise — notification must not block the
    watcher loop.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    text = f"Xteink wallpaper uploaded for {date}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_notification": False,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "xteink-watcher/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        if '"ok":true' in body.replace(" ", "").lower() or '"ok": true' in body:
            log.info("Telegram notification sent.")
        else:
            log.warning("Telegram API unexpected response: %s", body[:200])
    except Exception as exc:
        log.warning("Telegram notification failed: %s", exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Xteink watcher started. Polling %s every %ds.", STATUS_URL, POLL_INTERVAL)
    log.info("Upload timeout: %ds, max retries: %d", UPLOAD_TIMEOUT, MAX_RETRIES)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        log.info("Telegram notifications enabled (chat_id=%s).", TELEGRAM_CHAT_ID)
    else:
        log.info("Telegram notifications disabled (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID to enable).")

    last_logged_date = None
    last_logged_skip = None

    while True:
        date = today_str()

        # Log when the calendar date rolls over
        if last_logged_date != date:
            log.info("New day: %s — lock from previous day is now stale.", date)
            last_logged_date = date
            last_logged_skip = None

        if already_uploaded(date):
            if last_logged_skip != date:
                log.info("Already uploaded for %s. Polling in case device reconnects tomorrow.", date)
                last_logged_skip = date
            time.sleep(POLL_INTERVAL)
            continue

        if not device_online():
            time.sleep(POLL_INTERVAL)
            continue

        log.info("Device detected at %s.", DEVICE_IP)

        # Generate fresh BMP (captures today's Todoist tasks + Readwise quote)
        try:
            bmp_path = generate_eink(date)
        except Exception as exc:
            log.error("Generation failed: %s — will retry next poll.", exc)
            time.sleep(POLL_INTERVAL)
            continue

        success = run_upload_with_retries(bmp_path)
        if success:
            write_lockfile(date)
            notify_telegram(date)
            log.info(
                "Done for %s. Put the Xteink to sleep to see the new wallpaper.", date
            )
        else:
            # Don't write lockfile; try again when device is next detected
            log.info("Will retry upload on next device detection.")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
