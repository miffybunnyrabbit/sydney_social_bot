#!/usr/bin/env python3
"""Move one or more candidate accounts into the tracked list.

Usage: python approve.py handle1 [handle2 ...]
       python approve.py --list        # show pending candidates
       python approve.py --reject handle1 [handle2 ...]
"""

import sys

from src import config


def list_candidates():
    data = config.load_yaml(config.CANDIDATES_FILE, {"candidates": []})
    if not data["candidates"]:
        print("No pending candidates.")
        return
    for c in data["candidates"]:
        print(f"@{c['handle']:<30} found {c.get('found', '?')}  via {c.get('source', '?')}")


def approve(handles):
    candidates_data = config.load_yaml(config.CANDIDATES_FILE, {"candidates": []})
    accounts_data = config.load_yaml(config.ACCOUNTS_FILE, {"accounts": []})

    remaining = []
    approved = []
    for c in candidates_data["candidates"]:
        if c["handle"] in handles:
            accounts_data["accounts"].append(
                {"handle": c["handle"], "category": "approved-candidate", "note": f"approved; originally {c.get('source', '')}"}
            )
            approved.append(c["handle"])
        else:
            remaining.append(c)

    candidates_data["candidates"] = remaining
    config.save_yaml(config.ACCOUNTS_FILE, accounts_data)
    config.save_yaml(config.CANDIDATES_FILE, candidates_data)

    for h in approved:
        print(f"Approved @{h} -> config/accounts.yaml")
    missing = set(handles) - set(approved)
    for h in missing:
        print(f"Not found in candidates: @{h}")


def reject(handles):
    candidates_data = config.load_yaml(config.CANDIDATES_FILE, {"candidates": []})
    remaining = [c for c in candidates_data["candidates"] if c["handle"] not in handles]
    removed = len(candidates_data["candidates"]) - len(remaining)
    candidates_data["candidates"] = remaining
    config.save_yaml(config.CANDIDATES_FILE, candidates_data)
    print(f"Removed {removed} candidate(s).")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--list"]:
        list_candidates()
    elif args[0] == "--reject":
        reject(args[1:])
    else:
        approve(args)
