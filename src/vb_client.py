"""Thin subprocess wrapper around the `vb` (vibatchium) CLI.

Everything here shells out to the already-running vibatchium daemon via the
`vb` binary rather than talking to it directly — same interface a human
operator uses, so `vb logs` on the server shows exactly what this bot did.
"""

import json
import subprocess

from . import config


class VbError(RuntimeError):
    pass


def _run(*args, timeout=60):
    cmd = [config.VB_BIN, "--session", config.VB_SESSION, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise VbError(f"{' '.join(cmd)} -> {proc.returncode}: {proc.stderr.strip()}")
    return proc.stdout


def go(url, timeout=45):
    return _run("go", url, timeout=timeout)


def map_tree():
    """Returns the raw ARIA-tree text of the current page (used for regex-scraping links)."""
    raw = subprocess.run(
        [config.VB_BIN, "--json", "--session", config.VB_SESSION, "map"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if raw.returncode != 0:
        raise VbError(f"map -> {raw.returncode}: {raw.stderr.strip()}")
    return json.loads(raw.stdout)["text"]


def text():
    return _run("text")


def screenshot(path):
    _run("screenshot", "-o", str(path))
    return path


def scroll(dy=1500):
    _run("scroll", "--dy", str(dy))


def fill(ref, value):
    _run("fill", ref, value)


def click(ref):
    _run("click", ref)
