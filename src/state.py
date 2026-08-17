import json

from . import config


def load():
    if not config.STATE_FILE.exists():
        return {}
    with open(config.STATE_FILE) as f:
        return json.load(f)


def save(state):
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
