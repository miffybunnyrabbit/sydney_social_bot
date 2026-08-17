"""Scan tracked accounts for posts we haven't seen before, extract event
details from the genuinely-new ones, and notify Telegram."""

import logging
import re
import time

from . import config, extract, notify, state, vb_client

log = logging.getLogger(__name__)


def _post_urls_for_account(handle, tree_text):
    """DOM order on a profile grid == most-recent-first."""
    pattern = re.compile(r"-\s*/url:\s*(/" + re.escape(handle) + r"/(?:p|reel)/[A-Za-z0-9_-]+/)")
    seen = []
    for m in pattern.finditer(tree_text):
        url = m.group(1)
        if url not in seen:
            seen.append(url)
    return seen


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
        event = extract.extract_event(shot_path, caption, handle)
        if event:
            notify.send_photo(shot_path, notify.format_event(handle, event, post_url))
        else:
            log.info("Not an event post: %s", post_url)
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
