#!/usr/bin/env python3
"""
Generate a public-only index of gists for a given GitHub username
and update a target gist with a Markdown table.

Env:
  GITHUB_USERNAME   (required) GitHub handle to list PUBLIC gists from
  INDEX_GIST_ID     (required) The gist ID to overwrite (the index gist)
  GITHUB_TOKEN      (required for updating the gist; optional for listing)

  To run: uv run python gist-index.py
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests import Response, Session

API = "https://api.github.com"
TIMEOUT = 30  # seconds per request
RETRIES = 3   # light retry on transient 5xx / secondary rate limits
RETRY_BACKOFF = 2.0  # seconds (exponential)

USER_AGENT = "gist-index-script/1.0 (+https://github.com/)"

@dataclass
class Cfg:
    username: str
    index_gist_id: str
    token: Optional[str]

def getenv_required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"Missing required env: {name}", file=sys.stderr)
        sys.exit(1)
    return val

def load_cfg() -> Cfg:
    return Cfg(
        username=getenv_required("GITHUB_USERNAME"),
        index_gist_id=getenv_required("INDEX_GIST_ID"),
        token=os.getenv("GITHUB_TOKEN"),
    )

def make_session(token: Optional[str]) -> Session:
    s = requests.Session()
    s.headers.update({
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    })
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s

def _req_with_retry(s: Session, method: str, url: str, **kw: Any) -> Response:
    last_err: Optional[Exception] = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = s.request(method, url, timeout=TIMEOUT, **kw)
            # Handle primary and secondary rate limits gracefully
            if r.status_code == 403 and "rate limit" in (r.text or "").lower():
                reset = r.headers.get("X-RateLimit-Reset")
                if reset and reset.isdigit():
                    wait = max(0, int(reset) - int(time.time())) + 1
                    print(f"Rate limited. Sleeping {wait}s…", file=sys.stderr)
                    time.sleep(wait)
                    continue
            # Retry on transient 5xx
            if 500 <= r.status_code < 600:
                raise requests.HTTPError(f"{r.status_code} {r.reason}", response=r)
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            last_err = e
            if attempt == RETRIES:
                break
            sleep = RETRY_BACKOFF ** (attempt - 1)
            print(f"Transient error ({e}); retry {attempt}/{RETRIES-1} in {sleep:.1f}s…", file=sys.stderr)
            time.sleep(sleep)
    assert last_err is not None
    raise last_err

def list_public_gists(s: Session, username: str) -> List[Dict[str, Any]]:
    """List ALL public gists for a username (paginated)."""
    gists: List[Dict[str, Any]] = []
    page = 1
    while True:
        r = _req_with_retry(s, "GET", f"{API}/users/{username}/gists", params={"per_page": 100, "page": page})
        if r.status_code == 404:
            print(f"User '{username}' not found or gists unavailable.", file=sys.stderr)
            sys.exit(2)
        r.raise_for_status()
        chunk = r.json()
        if not chunk:
            break
        gists.extend(chunk)
        page += 1
    return gists

def primary_language(files: Dict[str, Dict[str, Any]]) -> str:
    """Pick language of largest file, if any."""
    best: Optional[Tuple[str, int]] = None
    for f in files.values():
        lang = f.get("language")
        size = int(f.get("size", 0) or 0)
        if lang and (best is None or size > best[1]):
            best = (lang, size)
    return best[0] if best else ""

def build_markdown(gists: List[Dict[str, Any]]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Gist Index (Public)",
        "",
        f"_Auto-generated daily at {now}_",
        "",
        "| Title | Files | Lang | Public | Updated | Link |",
        "|---|---:|---|:---:|---|---|",
    ]
    # newest updated first
    gists_sorted = sorted(gists, key=lambda x: x.get("updated_at") or "", reverse=True)
    for g in gists_sorted:
        desc = (g.get("description") or "").strip() or "(no description)"
        title = desc.splitlines()[0][:120]
        files = g.get("files") or {}
        file_count = len(files)
        lang = primary_language(files)
        public = "✅"  # listing public-only by design
        updated_raw = (g.get("updated_at") or "")
        # keep the original UTC indicator from GitHub but make it human-friendly
        updated = updated_raw.replace("T", " ").replace("Z", " UTC")
        url = g.get("html_url") or ""
        lines.append(f"| {title} | {file_count} | {lang} | {public} | {updated} | [open]({url}) |")
    lines.append("")
    return "\n".join(lines)

def update_index_gist(s: Session, gist_id: str, content_md: str) -> str:
    if "Authorization" not in s.headers:
        print("GITHUB_TOKEN is required to update the gist.", file=sys.stderr)
        sys.exit(3)
    payload = {
        "description": "Auto-generated index of my PUBLIC gists",
        "files": {"Public-Gists-by-Rich-Lewis.md": {"content": content_md}},
    }
    r = _req_with_retry(s, "PATCH", f"{API}/gists/{gist_id}", json=payload)
    if r.status_code == 404:
        print("INDEX_GIST_ID not found or token lacks access to that gist.", file=sys.stderr)
        sys.exit(4)
    r.raise_for_status()
    return r.json().get("html_url", "(unknown)")

def main() -> None:
    cfg = load_cfg()
    s = make_session(cfg.token)
    gists = list_public_gists(s, cfg.username)
    md = build_markdown(gists)
    url = update_index_gist(s, cfg.index_gist_id, md)
    print(f"Updated gist: {url}")

if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        status = getattr(e, "response", None).status_code if getattr(e, "response", None) else "HTTP"
        print(f"HTTP error ({status}): {e}", file=sys.stderr)
        sys.exit(5)
    except Exception as e:
        print(f"Unhandled error: {e!r}", file=sys.stderr)
        sys.exit(6)
