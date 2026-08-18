#!/usr/bin/env python3
"""Manual pipeline check: look at the newest post on the first N tracked
accounts (ignoring state.json), extract + notify for the first M posts that
turn out to be real events. Not part of the daily cron flow — just for
validating go -> screenshot -> extract -> Telegram end to end.

Usage: python test_scan.py [N_ACCOUNTS] [M_EVENTS]
"""

import sys
from datetime import date

from src import config, extract, notify, scan, vb_client

N_ACCOUNTS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
M_EVENTS = int(sys.argv[2]) if len(sys.argv) > 2 else 3

accounts = config.load_yaml(config.ACCOUNTS_FILE, {"accounts": []})["accounts"][:N_ACCOUNTS]

sent = 0
for account in accounts:
    if sent >= M_EVENTS:
        print(f"Hit {M_EVENTS} events, stopping early.")
        break

    handle = account["handle"]
    print(f"--- @{handle} ---")
    try:
        vb_client.go(f"https://www.instagram.com/{handle}/")
        tree = vb_client.map_tree()
    except vb_client.VbError as e:
        print(f"  profile load failed: {e}")
        continue

    post_paths = scan._post_urls_for_account(handle, tree)
    if not post_paths:
        print("  no posts found")
        continue

    path = post_paths[0]
    post_url = f"https://www.instagram.com{path}"
    try:
        vb_client.go(post_url)
        caption = vb_client.text()
        config.SCREENSHOT_DIR.mkdir(exist_ok=True)
        shot_path = config.SCREENSHOT_DIR / f"test_{handle}.png"
        vb_client.screenshot(shot_path)
    except vb_client.VbError as e:
        print(f"  post load failed: {e}")
        continue

    try:
        today = date.today()
        event = extract.extract_event(shot_path, caption, handle, reference_date=today)
        if not event:
            print("  not an event post")
        elif not scan._is_upcoming(event.get("date_iso", ""), today):
            print(f"  EVENT outside next {scan.EVENT_WINDOW_DAYS} days, skipping: {event.get('title')} (date_iso={event.get('date_iso')!r})")
        else:
            print(f"  EVENT: {event.get('title')}")
            notify.send_photo(shot_path, notify.format_event(handle, event, post_url))
            sent += 1
    finally:
        shot_path.unlink(missing_ok=True)

print(f"Done. Sent {sent} event notification(s).")
