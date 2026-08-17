#!/usr/bin/env python3
"""
Xteink wallpaper watcher for Synology NAS.

Polls the CrossPoint device on the local network.  When it appears (i.e. you
connect the Xteink to home WiFi on the File Upload screen):
  1. Generates today's e-ink BMP (fresh Todoist tasks + Readwise quote).
  2. Uploads it as sleep.bmp via the CrossPoint HTTP endpoint.
  3. Downloads latest Readwise Reader articles as EPUBs and uploads them.
  4. Writes per-day lockfiles so wallpaper/articles aren't re-pushed until
     tomorrow (article *downloads* remain incremental via reader_sync.json).

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
    READWISE_TOKEN       Required for quotes + Reader article sync
    READER_SYNC          Set to 0/false to disable article sync (default: on)
    READER_LOCATIONS     Comma-separated Reader locations (default: new)
    READER_MAX_ARTICLES  Max new articles to pull per sync (default: 25)
"""

import ipaddress
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

# Ensure project root is importable when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEVICE_IP = os.environ.get("DEVICE_IP", "10.0.0.164").strip()
try:
    # Reject hostnames / odd values so STATUS_URL cannot be steered off-LAN.
    DEVICE_IP = str(ipaddress.IPv4Address(DEVICE_IP))
except ValueError as exc:
    raise SystemExit(f"DEVICE_IP must be an IPv4 address, got {DEVICE_IP!r}") from exc

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "20"))
UPLOAD_TIMEOUT = int(os.environ.get("UPLOAD_TIMEOUT", "300"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip().strip("'\"")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip().strip("'\"")

_READER_SYNC_RAW = os.environ.get("READER_SYNC", "1").strip().lower()
READER_SYNC_ENABLED = _READER_SYNC_RAW not in ("0", "false", "no", "off")
READER_LOCATIONS = os.environ.get("READER_LOCATIONS", "new").strip()
READER_MAX_ARTICLES = int(os.environ.get("READER_MAX_ARTICLES", "25"))

APP_DIR = Path(__file__).parent.parent
OUTPUT_DIR = APP_DIR / "output" / "eink"
READER_OUTPUT_DIR = APP_DIR / "output" / "reader"
STATE_DIR = APP_DIR / "state"
READER_STATE_PATH = STATE_DIR / "reader_sync.json"

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


def reader_lockfile_path(date: str) -> Path:
    return STATE_DIR / f"reader_uploaded_{date}"


def already_uploaded(date: str) -> bool:
    return lockfile_path(date).exists()


def reader_already_uploaded(date: str) -> bool:
    return reader_lockfile_path(date).exists()


def write_lockfile(date: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lockfile_path(date).write_text(
        f"Uploaded at {datetime.now().isoformat()}\n"
    )


def write_reader_lockfile(date: str, count: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    reader_lockfile_path(date).write_text(
        f"Reader sync at {datetime.now().isoformat()} ({count} file(s))\n"
    )


def probe_device(ip: str, timeout: int = 10) -> tuple[bool, str]:
    """
    Probe CrossPoint /api/status at ip.

    Returns (online, detail). online is True only when JSON has device == "X4".
    Does not follow redirects (avoids SSRF-style probes under host networking).
    """
    status_url = f"http://{ip}/api/status"
    try:
        req = urllib.request.Request(
            status_url,
            headers={"User-Agent": "xteink-watcher/1.0"},
        )

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(req, timeout=timeout) as resp:
            http_status = getattr(resp, "status", 200)
            body = resp.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return False, f"{status_url} HTTP {http_status} non-JSON: {body[:120]!r}"
        device = str(data.get("device", "")).upper()
        if device == "X4":
            return True, (
                f"{status_url} ok device={device} "
                f"ip={data.get('ip', '?')} mode={data.get('mode', '?')} "
                f"rssi={data.get('rssi', '?')}"
            )
        return False, (
            f"{status_url} HTTP {http_status} JSON ok but device={device!r} "
            f"(need 'X4'). keys={sorted(data)[:12]}"
        )
    except TimeoutError:
        return False, f"{status_url} timed out (device off, wrong IP, or not on File Upload)"
    except urllib.error.HTTPError as exc:
        return False, f"{status_url} HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"{status_url} unreachable: {exc.reason}"
    except Exception as exc:
        return False, f"{status_url} {type(exc).__name__}: {exc}"


def device_online() -> bool:
    """
    Return True if the CrossPoint device responds on its status endpoint.

    Requires JSON with device == "X4" (not merely a non-empty HTTP body).
    Flaky WiFi is expected; failures are normal.
    """
    ok, detail = probe_device(DEVICE_IP)
    if not ok:
        device_online.last_error = detail  # type: ignore[attr-defined]
    else:
        device_online.last_error = ""  # type: ignore[attr-defined]
    return ok


device_online.last_error = ""  # type: ignore[attr-defined]


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


def upload_file(local_path: Path, remote_filename: str) -> bool:
    """
    Upload a local file to the CrossPoint device using curl.

    Uses the same flags as the known-good upload_wallpaper.sh:
      -H "Expect:"          prevents 100-continue issues with the device
      --max-time 300        device has weak WiFi; uploads can be very slow
      -F "file=@..;filename=<remote_filename>"

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
        "-F", f"file=@{local_path};filename={remote_filename}",
        UPLOAD_URL,
    ]
    log.info("Uploading %s → %s to %s ...", local_path.name, remote_filename, UPLOAD_URL)
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


def upload(bmp_path: Path) -> bool:
    """Upload bmp_path as sleep.bmp (wallpaper convenience wrapper)."""
    return upload_file(bmp_path, "sleep.bmp")


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


def sync_and_upload_reader_articles() -> int:
    """
    Pull new Reader articles and upload each file to the CrossPoint device.

    Returns the number of files successfully uploaded. Raises on hard API
    misconfiguration; upload failures are logged and counted as incomplete.
    """
    from src.reader import parse_locations, sync_articles

    READER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    locations = parse_locations(READER_LOCATIONS)
    log.info(
        "Syncing Reader articles (locations=%s, max=%d) ...",
        ",".join(locations),
        READER_MAX_ARTICLES,
    )
    exported = sync_articles(
        READER_OUTPUT_DIR,
        READER_STATE_PATH,
        locations=locations,
        max_documents=READER_MAX_ARTICLES,
    )
    if not exported:
        log.info("No new Reader articles to upload.")
        return 0

    uploaded = 0
    for path in exported:
        ok = False
        for attempt in range(1, MAX_RETRIES + 1):
            if upload_file(path, path.name):
                ok = True
                break
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                log.info("Article retry %d/%d in %ds ...", attempt, MAX_RETRIES, wait)
                time.sleep(wait)
        if ok:
            uploaded += 1
        else:
            log.warning("Gave up uploading article: %s", path.name)

    log.info("Uploaded %d/%d Reader article(s).", uploaded, len(exported))
    return uploaded


def notify_telegram(
    date: str,
    *,
    wallpaper_just_uploaded: bool = False,
    articles_uploaded: int = 0,
) -> None:
    """
    Send a Telegram message on successful upload.

    No-op if TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is unset.
    Failures are logged but never raise — notification must not block the
    watcher loop.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    # Numeric chat IDs should be sent as ints; usernames stay strings.
    chat_id: object = TELEGRAM_CHAT_ID
    if TELEGRAM_CHAT_ID.lstrip("-").isdigit():
        chat_id = int(TELEGRAM_CHAT_ID)

    parts = []
    if wallpaper_just_uploaded:
        parts.append(f"wallpaper for {date}")
    if articles_uploaded:
        noun = "article" if articles_uploaded == 1 else "articles"
        parts.append(f"{articles_uploaded} Reader {noun}")
    if not parts:
        return
    text = "Xteink upload: " + " + ".join(parts)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
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
        data = json.loads(body)
        if data.get("ok"):
            log.info("Telegram notification sent.")
        else:
            log.warning("Telegram API error: %s", data.get("description", body[:200]))
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
            err_data = json.loads(err_body)
            detail = err_data.get("description", err_body[:300])
        except Exception:
            detail = err_body[:300] or str(exc)
        log.warning("Telegram notification failed (HTTP %s): %s", exc.code, detail)
    except Exception as exc:
        log.warning("Telegram notification failed: %s", exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    READER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Xteink watcher started. Polling %s every %ds.", STATUS_URL, POLL_INTERVAL)
    log.info("Upload timeout: %ds, max retries: %d", UPLOAD_TIMEOUT, MAX_RETRIES)
    if READER_SYNC_ENABLED:
        log.info(
            "Reader article sync enabled (locations=%s, max=%d).",
            READER_LOCATIONS,
            READER_MAX_ARTICLES,
        )
    else:
        log.info("Reader article sync disabled (set READER_SYNC=1 to enable).")
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        log.info("Telegram notifications enabled (chat_id=%s).", TELEGRAM_CHAT_ID)
    else:
        log.info("Telegram notifications disabled (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID to enable).")

    last_logged_date = None
    last_logged_skip = None
    last_waiting_log = 0.0
    waiting_log_every = max(POLL_INTERVAL * 6, 60)  # ~2 min at default 20s poll

    while True:
        date = today_str()

        # Log when the calendar date rolls over
        if last_logged_date != date:
            log.info("New day: %s — lock from previous day is now stale.", date)
            last_logged_date = date
            last_logged_skip = None

        wallpaper_done = already_uploaded(date)
        reader_done = (not READER_SYNC_ENABLED) or reader_already_uploaded(date)

        if wallpaper_done and reader_done:
            if last_logged_skip != date:
                log.info(
                    "Already uploaded wallpaper%s for %s. Polling until tomorrow.",
                    " + Reader articles" if READER_SYNC_ENABLED else "",
                    date,
                )
                last_logged_skip = date
            time.sleep(POLL_INTERVAL)
            continue

        if not device_online():
            now = time.monotonic()
            if now - last_waiting_log >= waiting_log_every:
                pending = []
                if not wallpaper_done:
                    pending.append("wallpaper")
                if READER_SYNC_ENABLED and not reader_done:
                    pending.append("Reader articles")
                log.info(
                    "Waiting for device at %s (still need: %s). Last probe: %s",
                    DEVICE_IP,
                    ", ".join(pending) or "nothing",
                    device_online.last_error or "no response",
                )
                last_waiting_log = now
            time.sleep(POLL_INTERVAL)
            continue

        log.info("Device detected at %s.", DEVICE_IP)
        articles_uploaded = 0
        wallpaper_just_uploaded = False

        # Generate + upload wallpaper if not yet done today
        if not wallpaper_done:
            try:
                bmp_path = generate_eink(date)
            except Exception as exc:
                log.error("Generation failed: %s — will retry next poll.", exc)
                time.sleep(POLL_INTERVAL)
                continue

            success = run_upload_with_retries(bmp_path)
            if success:
                write_lockfile(date)
                wallpaper_done = True
                wallpaper_just_uploaded = True
                log.info("Wallpaper uploaded for %s.", date)
            else:
                # Don't write lockfile; try again when device is next detected
                log.info("Will retry wallpaper upload on next device detection.")
                time.sleep(POLL_INTERVAL)
                continue

        # Pull + upload new Reader articles while the File Upload screen is up
        if READER_SYNC_ENABLED and not reader_done:
            try:
                articles_uploaded = sync_and_upload_reader_articles()
                write_reader_lockfile(date, articles_uploaded)
                reader_done = True
            except Exception as exc:
                log.error("Reader sync/upload failed: %s — will retry next poll.", exc)
                time.sleep(POLL_INTERVAL)
                continue

        if wallpaper_just_uploaded or articles_uploaded:
            notify_telegram(
                date,
                wallpaper_just_uploaded=wallpaper_just_uploaded,
                articles_uploaded=articles_uploaded,
            )
            log.info(
                "Done for %s. Put the Xteink to sleep to see the new wallpaper%s.",
                date,
                f" ({articles_uploaded} article(s) added)" if articles_uploaded else "",
            )
        elif wallpaper_done and reader_done:
            log.info("Nothing new to upload for %s.", date)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
