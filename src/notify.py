import logging

import requests

from . import config

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


def _post(method, **payload):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID) — skipping send: %s", payload)
        return
    url = API.format(token=config.TELEGRAM_BOT_TOKEN, method=method)
    payload.setdefault("chat_id", config.TELEGRAM_CHAT_ID)
    resp = requests.post(url, data=payload, timeout=30)
    if not resp.ok:
        log.error("Telegram %s failed: %s %s", method, resp.status_code, resp.text)


def send_message(text):
    # Telegram HTML parse mode wants a small tag subset; strip anything else.
    _post("sendMessage", text=text, parse_mode="HTML", disable_web_page_preview=False)


def send_photo(path, caption=""):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — skipping photo send")
        return
    url = API.format(token=config.TELEGRAM_BOT_TOKEN, method="sendPhoto")
    with open(path, "rb") as f:
        resp = requests.post(
            url,
            data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"photo": f},
            timeout=60,
        )
    if not resp.ok:
        log.error("Telegram sendPhoto failed: %s %s", resp.status_code, resp.text)


def format_event(account_handle, event, post_url):
    lines = [f"<b>{_escape(event.get('title') or account_handle)}</b>", f"via @{account_handle}"]
    if event.get("when"):
        lines.append(f"🕐 {_escape(event['when'])}")
    if event.get("where"):
        lines.append(f"📍 {_escape(event['where'])}")
    if event.get("cost"):
        lines.append(f"💰 {_escape(event['cost'])}")
    if event.get("who"):
        lines.append(f"👥 {_escape(event['who'])}")
    if event.get("notes"):
        lines.append(_escape(event["notes"]))
    lines.append(f'<a href="{post_url}">Open post</a>')
    return "\n".join(lines)


def _escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
