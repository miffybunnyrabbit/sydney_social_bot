#!/usr/bin/env python3
"""Daily entrypoint: scan tracked accounts for new events, then run a slice
of account discovery. Meant to be invoked once a day by cron (see
setup/crontab.example) — vibatchium's daemon + the logged-in `instagram`
session should already be running persistently on the host.
"""

import fcntl
import logging
import os
import sys

from src import config, discover, notify, scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("main")

LOCK_FILE = config.ROOT / "main.lock"


def _acquire_lock():
    """Refuse to run if another instance is already going — vibatchium's
    session is a single shared browser, two runs fighting over it produces
    exactly the kind of "wrong page" confusion that's hard to debug."""
    fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return None
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def main():
    log.info("=== sydney_social_bot run start ===")
    try:
        scan.run()
    except Exception:
        log.exception("Scan step failed")
        notify.send_message("⚠️ sydney_social_bot: scan step crashed, check logs.")

    try:
        discover.run()
    except Exception:
        log.exception("Discovery step failed")
        notify.send_message("⚠️ sydney_social_bot: discovery step crashed, check logs.")

    log.info("=== sydney_social_bot run end ===")


if __name__ == "__main__":
    lock = _acquire_lock()
    if lock is None:
        log.warning("Another run is already in progress (main.lock held) — exiting.")
        sys.exit(1)

    if not config.ANTHROPIC_API_KEY:
        log.warning("ANTHROPIC_API_KEY is not set — event posts will be detected but not extracted.")
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("Telegram is not configured — nothing will actually be sent.")
    try:
        main()
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    sys.exit(0)
