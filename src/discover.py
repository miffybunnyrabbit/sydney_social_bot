"""Find new candidate accounts: IG-search sweep + collab-tag mining.

Both techniques were worked out by hand before this bot existed (see
config/discovery.yaml comments). Results are never auto-added to
accounts.yaml — they land in candidates.yaml and get one Telegram summary
message, per the "queue for approval" design. Use approve.py to promote
one into accounts.yaml.
"""

import datetime
import logging
import re
import time

from . import config, notify, vb_client

log = logging.getLogger(__name__)

HANDLE_FROM_PROFILE_LINK_RE = re.compile(r"link \"([a-zA-Z0-9._]+)'s profile picture")
TAGGED_CAPTION_RE = re.compile(r'link "Photo (?:by|shared by)[^"]*"')
AT_HANDLE_RE = re.compile(r"@([a-zA-Z0-9._]+)")
SEARCH_INPUT_REF_RE = re.compile(r'textbox "Search input"(?: \[active\])? @(e\d+)')


def _rotate_slice(items, per_run):
    if not items or per_run <= 0:
        return []
    n = len(items)
    per_run = min(per_run, n)
    offset = (datetime.date.today().toordinal() * per_run) % n
    return [items[(offset + i) % n] for i in range(per_run)]


def _search_handles(query):
    vb_client.go("https://www.instagram.com/explore/")
    tree = vb_client.map_tree()
    m = SEARCH_INPUT_REF_RE.search(tree)
    if not m:
        log.warning("Couldn't find search box while searching %r", query)
        return set()
    ref = "@" + m.group(1)
    vb_client.fill(ref, query)
    time.sleep(1.2)
    tree = vb_client.map_tree()
    return set(HANDLE_FROM_PROFILE_LINK_RE.findall(tree))


def _tagged_hub_handles(hub_handle):
    vb_client.go(f"https://www.instagram.com/{hub_handle}/tagged/")
    time.sleep(1)
    for _ in range(5):
        vb_client.scroll(dy=1500)
        time.sleep(0.5)
    tree = vb_client.map_tree()
    found = set()
    for caption_match in TAGGED_CAPTION_RE.finditer(tree):
        for handle in AT_HANDLE_RE.findall(caption_match.group(0)):
            found.add(handle.rstrip("."))  # trailing "." is sentence punctuation, not part of the handle
    return found


def run():
    discovery = config.load_yaml(config.DISCOVERY_FILE, {})
    queries = discovery.get("search_queries", [])
    hubs = discovery.get("tagged_hub_accounts", [])
    noise = set(discovery.get("noise_handles", []))

    known = set(config.tracked_handles()) | set(config.candidate_handles()) | noise

    new_finds = {}  # handle -> source note

    for query in _rotate_slice(queries, config.DISCOVERY_QUERIES_PER_RUN):
        try:
            for handle in _search_handles(query):
                if handle not in known and handle not in new_finds:
                    new_finds[handle] = f"search: \"{query}\""
        except vb_client.VbError as e:
            log.error("Search %r failed: %s", query, e)
        time.sleep(config.SCAN_DELAY_SECONDS)

    for hub in _rotate_slice(hubs, config.DISCOVERY_HUBS_PER_RUN):
        try:
            for handle in _tagged_hub_handles(hub):
                if handle not in known and handle not in new_finds and handle != hub:
                    new_finds[handle] = f"tagged-tab of @{hub}"
        except vb_client.VbError as e:
            log.error("Tagged-tab scan of @%s failed: %s", hub, e)
        time.sleep(config.SCAN_DELAY_SECONDS)

    if not new_finds:
        log.info("Discovery run: nothing new.")
        return

    candidates_data = config.load_yaml(config.CANDIDATES_FILE, {"candidates": []})
    today = datetime.date.today().isoformat()
    for handle, source in new_finds.items():
        candidates_data["candidates"].append({"handle": handle, "found": today, "source": source})
    config.save_yaml(config.CANDIDATES_FILE, candidates_data)

    lines = [f"🔎 <b>{len(new_finds)} new candidate account(s)</b> found — review and approve:"]
    for handle, source in new_finds.items():
        lines.append(f"• <a href=\"https://www.instagram.com/{handle}/\">@{handle}</a> ({source})")
    lines.append("\nRun <code>python approve.py &lt;handle&gt; [handle...]</code> to add one to the tracked list.")
    notify.send_message("\n".join(lines))
    log.info("Discovery run: %d new candidates.", len(new_finds))
