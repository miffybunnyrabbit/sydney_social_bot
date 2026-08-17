#!/usr/bin/env python3
"""Daily entrypoint: scan tracked accounts for new events, then run a slice
of account discovery. Meant to be invoked once a day by cron (see
setup/crontab.example) — vibatchium's daemon + the logged-in `instagram`
session should already be running persistently on the host.
"""

import logging
import sys

from src import config, discover, notify, scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("main")


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
    if not config.ANTHROPIC_API_KEY:
        log.warning("ANTHROPIC_API_KEY is not set — event posts will be detected but not extracted.")
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("Telegram is not configured — nothing will actually be sent.")
    main()
    sys.exit(0)
