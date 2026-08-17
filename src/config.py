import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

VB_BIN = os.environ.get("VB_BIN", "vb")
VB_SESSION = os.environ.get("VB_SESSION", "instagram")

POSTS_PER_ACCOUNT = int(os.environ.get("POSTS_PER_ACCOUNT", "3"))
DISCOVERY_QUERIES_PER_RUN = int(os.environ.get("DISCOVERY_QUERIES_PER_RUN", "8"))
DISCOVERY_HUBS_PER_RUN = int(os.environ.get("DISCOVERY_HUBS_PER_RUN", "2"))
SCAN_DELAY_SECONDS = float(os.environ.get("SCAN_DELAY_SECONDS", "2"))

ACCOUNTS_FILE = ROOT / "config" / "accounts.yaml"
CANDIDATES_FILE = ROOT / "config" / "candidates.yaml"
DISCOVERY_FILE = ROOT / "config" / "discovery.yaml"
STATE_FILE = ROOT / "state.json"
SCREENSHOT_DIR = ROOT / "screenshots"


def load_yaml(path, default):
    if not path.exists():
        return default
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if data is not None else default


def save_yaml(path, data):
    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, width=100)


def tracked_handles():
    data = load_yaml(ACCOUNTS_FILE, {"accounts": []})
    return [a["handle"] for a in data.get("accounts", [])]


def candidate_handles():
    data = load_yaml(CANDIDATES_FILE, {"candidates": []})
    return [c["handle"] for c in data.get("candidates", [])]
