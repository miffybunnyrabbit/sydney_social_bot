"""Scan tracked accounts for posts we haven't seen before, extract event
details from the genuinely-new ones, and notify Telegram."""

import logging
import re
import time
from datetime import date, datetime, timedelta

from . import config, extract, notify, state, vb_client

log = logging.getLogger(__name__)

EVENT_WINDOW_DAYS = 7


def _is_upcoming(date_iso, today):
    """True if date_iso falls within [today, today + EVENT_WINDOW_DAYS]."""
    if not date_iso:
        return False
    try:
        event_date = datetime.strptime(date_iso, "%Y-%m-%d").date()
    except ValueError:
        return False
    return today <= event_date <= today + timedelta(days=EVENT_WINDOW_DAYS)


_ALT_DATE_RE = re.compile(r"\bon ([A-Z][a-z]+ \d{1,2}, \d{4})")


def _parse_alt_date(alt_text):
    """Instagram's own alt text on grid thumbnails embeds the real post
    date for photos/carousels, e.g. 'Photo by X on June 23, 2022.' (Reels
    usually don't get one.) None if no date is present or parseable."""
    m = _ALT_DATE_RE.search(alt_text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%B %d, %Y").date()
    except ValueError:
        return None


def _post_urls_for_account(handle, tree_text):
    """DOM order on a profile grid is normally most-recent-first, but
    pinned posts (Instagram allows up to 3) stay at the top regardless of
    age. We use the real dates embedded in each thumbnail's alt text to
    detect dated posts sitting out of chronological order at the front of
    the grid and move them behind the actual newest one. Undated entries
    (typically Reels) are left in place since we have no evidence either way."""
    pattern = re.compile(
        r'link "([^"]*)"[^\n]*\n\s*-\s*/url:\s*(/' + re.escape(handle) + r"/(?:p|reel)/[A-Za-z0-9_-]+/)"
    )
    entries = []
    seen = set()
    for m in pattern.finditer(tree_text):
        alt_text, url = m.group(1), m.group(2)
        if url in seen:
            continue
        seen.add(url)
        entries.append((url, _parse_alt_date(alt_text)))

    dated = [d for _, d in entries if d is not None]
    if not dated:
        return [url for url, _ in entries]

    newest_date = max(dated)
    pinned = []
    i = 0
    while i < len(entries) and entries[i][1] is not None and entries[i][1] < newest_date:
        pinned.append(entries[i])
        i += 1

    if pinned:
        log.info(
            "@%s: %d post(s) at the top of the grid are older than the newest dated post — "
            "likely pinned, moving behind it: %s",
            handle, len(pinned), ", ".join(url for url, _ in pinned),
        )

    ordered = entries[i:] + pinned
    return [url for url, _ in ordered]


def _process_post(handle, path):
    post_url = f"https://www.instagram.com{path}"
    log.info("New post for @%s: %s", handle, post_url)
    try:
        vb_client.go(post_url)
        caption = vb_client.text()
        config.SCREENSHOT_DIR.mkdir(exist_ok=True)
        shot_path = config.SCREENSHOT_DIR / f"{handle}_{path.strip('/').split('/')[-1]}.png"
        vb_client.screenshot(shot_path)
    except vb_client.VbError as e:
        log.error("Failed to load post %s: %s", post_url, e)
        return

    try:
        today = date.today()
        event = extract.extract_event(shot_path, caption, handle, reference_date=today)
        if not event:
            log.info("Not an event post: %s", post_url)
        elif not _is_upcoming(event.get("date_iso", ""), today):
            log.info(
                "Event outside next %d days, skipping: %s (date_iso=%r)",
                EVENT_WINDOW_DAYS, post_url, event.get("date_iso"),
            )
        else:
            notify.send_photo(shot_path, notify.format_event(handle, event, post_url))
    finally:
        shot_path.unlink(missing_ok=True)


def scan_account(handle, st):
    log.info("Scanning @%s", handle)
    try:
        vb_client.go(f"https://www.instagram.com/{handle}/")
        tree = vb_client.map_tree()
    except vb_client.VbError as e:
        log.error("Failed to load @%s: %s", handle, e)
        return

    post_paths = _post_urls_for_account(handle, tree)[: config.POSTS_PER_ACCOUNT]
    if not post_paths:
        log.warning("No posts found on @%s (private, empty, or walled)", handle)
        return

    newest = post_paths[0]
    last_seen = st.get(handle)

    if last_seen is None:
        # First run for this account — baseline it instead of dumping
        # historical posts into the chat.
        st[handle] = newest
        return

    if last_seen == newest:
        return

    if last_seen in post_paths:
        new_paths = post_paths[: post_paths.index(last_seen)]
    else:
        # last_seen has fallen off the top N — several posts happened
        # since the last run. Only backfill what we fetched this pass.
        new_paths = post_paths

    for path in reversed(new_paths):  # oldest-first, so Telegram reads chronologically
        _process_post(handle, path)

    st[handle] = newest


def run():
    st = state.load()
    accounts = config.load_yaml(config.ACCOUNTS_FILE, {"accounts": []})["accounts"]
    for account in accounts:
        scan_account(account["handle"], st)
        state.save(st)  # incremental save so a mid-run crash doesn't lose progress
        time.sleep(config.SCAN_DELAY_SECONDS)
