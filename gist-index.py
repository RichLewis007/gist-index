#!/usr/bin/env python3
"""
Generate a public-only index of my gists,
and update a target gist with a Markdown table of those public gists.

Reminder

The workflow cron is 0 13 * * * (13:00 UTC), which is 9:00 AM ET during Daylight Time. If you ever change the schedule, update SCHEDULE_DESC to match.

## Behavior
- Always prints the Markdown to stdout.
- If INDEX_GIST_ID and GITHUB_TOKEN are set, also PATCHes that gist file.

Uses a GitHub Action which runs this script on a schedule or manually.

## Requirements
Uses GitHub API command line utility, install it via:
```
gh auth login
```

This script is using the python tool "uv". If you aren't, you can install it via pip:
```
pip install uv
```

or if you don't want to use uv, install deps via:
```
python3 -m pip install --upgrade requests
```
and run via:
```
python3 gist-index.py
```

Env:
  GITHUB_USERNAME   (required) GitHub handle to list PUBLIC gists from
  INDEX_GIST_ID     (required) The gist ID to overwrite (the index gist)
  GITHUB_TOKEN      (has "gist" scope, required for updating the gist; optional for listing)

  To run: 
  export GITHUB_USERNAME="RichLewis007"
  export INDEX_GIST_ID="YOUR_GIST_ID"
  export GITHUB_TOKEN="YOUR_GIST_EDITING_TOKEN"

  # If you added pyproject.toml with requests, plain `uv run` is enough:
  uv run python gist-index.py
  # Otherwise, pull requests on the fly:
  uv run --with requests python gist-index.py

  You'll see: Updated gist: https://gist.github.com/RichLewis007/a48c0ac6b651a36724ce6314d5242c74

## Output

Output fields:
Title (first line of gist description, truncated)
Files (count)
Lang (primary language by largest file)
Public (always ✅ here)
Updated (UTC)
Link (to the gist)

"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests import Response, Session

API = "https://api.github.com"
TIMEOUT = 30
RETRIES = 3
RETRY_BACKOFF = 2.0
USER_AGENT = "gist-index-script/1.1 (+https://github.com/)"
SCHEDULE_DESC = "Updated daily at 9:00 AM Eastern"  # keep this in sync with your cron

@dataclass
class Cfg:
    username: str
    index_gist_id: Optional[str]
    token: Optional[str]
    target_md: str

def getenv_required(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"Missing required env: {name}", file=sys.stderr)
        sys.exit(1)
    return v

def load_cfg() -> Cfg:
    return Cfg(
        username=getenv_required("GITHUB_USERNAME"),
        index_gist_id=os.getenv("INDEX_GIST_ID"),
        token=os.getenv("GITHUB_TOKEN"),
        target_md=os.getenv("TARGET_MD_FILENAME", "Public-Gists-by-Rich-Lewis.md"),
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
    last: Optional[Exception] = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = s.request(method, url, timeout=TIMEOUT, **kw)
            if r.status_code == 403 and "rate limit" in (r.text or "").lower():
                reset = r.headers.get("X-RateLimit-Reset")
                if reset and reset.isdigit():
                    wait = max(0, int(reset) - int(time.time())) + 1
                    print(f"Rate limited. Sleeping {wait}s…", file=sys.stderr)
                    time.sleep(wait)
                    continue
            if 500 <= r.status_code < 600:
                raise requests.HTTPError(f"{r.status_code} {r.reason}", response=r)
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            last = e
            if attempt == RETRIES:
                break
            backoff = RETRY_BACKOFF ** (attempt - 1)
            print(f"Transient error ({e}); retry {attempt}/{RETRIES-1} in {backoff:.1f}s…", file=sys.stderr)
            time.sleep(backoff)
    assert last is not None
    raise last

def list_public_gists(s: Session, username: str) -> List[Dict[str, Any]]:
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
    best: Optional[Tuple[str, int]] = None
    for f in files.values():
        lang = f.get("language")
        size = int(f.get("size", 0) or 0)
        if lang and (best is None or size > best[1]):
            best = (lang, size)
    return best[0] if best else ""

def build_markdown(gists: list[dict]) -> str:
    # Eastern time for display (handles EST/EDT automatically)
    now_et = datetime.now(ZoneInfo("America/New_York"))
    timestamp = now_et.strftime("%Y-%m-%d %I:%M %p %Z")

   # ---- styles (inline) ----
    style = """
<style>
:root { --line:#e5e7eb; --bg:#ffffff; --bg-alt:#fafafa; --text:#0f172a; --muted:#64748b; --hint:#94a3b8; }
.controls { display:flex; gap:.5rem; align-items:center; margin:.5rem 0 1rem; flex-wrap: wrap; }
.controls input[type="search"]{ padding:.45rem .6rem; width:260px; border:1px solid var(--line); border-radius:.5rem; }
.badge { display:inline-block; padding:.15rem .45rem; border-radius:.5rem; background:#e8efff; color:#1d4ed8; font-size:.75rem; line-height:1; }
.table-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:.95rem; background:var(--bg); }
thead th { position:sticky; top:0; background:var(--bg); text-align:left; border-bottom:1px solid var(--line); padding:.55rem .6rem; }
tbody td { border-top:1px solid var(--line); padding:.5rem .6rem; vertical-align:top; }
tbody tr:nth-child(even){ background:var(--bg-alt); }
th.sortable { cursor:pointer; }
th.sortable::after { content:" \\2195"; color:var(--hint); font-weight:normal; }
small.muted{ color:var(--muted); }
</style>
""".strip()

    lines = [
        "# Public Gists by Rich Lewis",
        "",
        style,
        f"_Auto-generated at {timestamp}_",
        "",
        "**Last updated:** " + timestamp,
        "",
        '<div class="controls">',
        '  <input id="filter" type="search" placeholder="Filter by title or language…">',
        '  <span class="badge" id="count"></span>',
        '</div>',
        '<div class="table-wrap" markdown="1">',
        "| Title | Files | Lang | Public | Updated | Link |",
        "|---|---:|---|:---:|---|---|",
    ]

    # newest first
    gists_sorted = sorted(gists, key=lambda x: x.get("updated_at") or "", reverse=True)
    for g in gists_sorted:
        desc = (g.get("description") or "").strip() or "(no description)"
        title = desc.splitlines()[0][:120]
        files = g.get("files") or {}
        file_count = len(files)
        lang = primary_language(files)
        # Convert UTC -> Eastern for display
        try:
            raw = g.get("updated_at")
            dt_utc = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
            updated = dt_et.strftime("%Y-%m-%d %I:%M %p %Z")
        except Exception:
            updated = g.get("updated_at") or ""
        url = g.get("html_url") or ""

        # Wrap language as a badge
        lang_cell = f'<span class="badge">{lang}</span>' if lang else ""

        lines.append(f"| {title} | {file_count} | {lang_cell} | ✅ | {updated} | [open]({url}) |")

    lines += [
        "</div>",
        "",
        (
            f"_Generated automatically by "
            f"[gist-index workflow](https://github.com/RichLewis007/gist-index). "
            f"{SCHEDULE_DESC}._"
        ),
        "",
        # ---- behavior (filter + sort) ----
        """<script>
(function(){
  const q=document.getElementById('filter');
  const table=document.querySelector('table'); if(!table) return;
  const tbody=table.tBodies[0]; const rows=[...tbody.rows];
  const ths=table.tHead? table.tHead.rows[0].cells : [];
  const count=document.getElementById('count');
  // mark sortable columns: Title(0), Files(1), Lang(2), Updated(4)
  [0,1,2,4].forEach(i=>ths[i] && ths[i].classList.add('sortable'));

  function applyFilter(){
    const term=(q?.value||"").toLowerCase();
    let visible=0;
    rows.forEach(tr=>{
      const text=tr.textContent.toLowerCase();
      const show=!term || text.includes(term);
      tr.style.display=show?"":"none";
      if(show) visible++;
    });
    if(count){ count.textContent = visible + " gists"; }
  }
  q && q.addEventListener('input', applyFilter);
  applyFilter();

  function cellVal(tr,i){
    const t=(tr.cells[i]?.textContent||"").trim();
    return t;
  }

  function sortBy(idx){
    let asc = !ths[idx].dataset.desc;
    rows.sort((a,b)=>{
      const A=cellVal(a,idx), B=cellVal(b,idx);
      // try date
      if(!isNaN(Date.parse(A)) && !isNaN(Date.parse(B))){
        return asc ? (new Date(A)-new Date(B)) : (new Date(B)-new Date(A));
      }
      // try number
      const nA=parseFloat(A), nB=parseFloat(B);
      if(!isNaN(nA) && !isNaN(nB)){ return asc ? (nA-nB) : (nB-nA); }
      // fallback string
      return asc ? A.localeCompare(B) : B.localeCompare(A);
    });
    rows.forEach(r=>tbody.appendChild(r));
    // toggle state
    ths[idx].dataset.desc = asc ? "" : "1";
  }

  [0,1,2,4].forEach(i=>{
    if(!ths[i]) return;
    ths[i].addEventListener('click', ()=>sortBy(i));
  });

  // Re-apply filter after sort to keep count correct
  table.addEventListener('click', e=>{
    if(e.target.closest('th')) setTimeout(applyFilter, 0);
  });

  // Support Material's client-side swaps if this ever sits behind it
  if(window.document$){ window.document$.subscribe(applyFilter); }
})();
</script>"""
    ]
    return "\n".join(lines)

    gists_sorted = sorted(gists, key=lambda x: x.get("updated_at") or "", reverse=True)
    for g in gists_sorted:
        desc = (g.get("description") or "").strip() or "(no description)"
        title = desc.splitlines()[0][:120]
        files = g.get("files") or {}
        file_count = len(files)
        lang = primary_language(files)

        # Convert GitHub's UTC timestamp to Eastern
        try:
            raw = g.get("updated_at")
            dt_utc = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
            updated = dt_et.strftime("%Y-%m-%d %I:%M %p %Z")
        except Exception:
            updated = g.get("updated_at") or ""

        url = g.get("html_url") or ""
        lines.append(f"| {title} | {file_count} | {lang} | ✅ | {updated} | [open]({url}) |")

    lines.append("")
    lines.append(
        f"_Generated automatically by "
        f"[gist-index workflow](https://github.com/RichLewis007/gist-index). "
        f"{SCHEDULE_DESC}._"
    )
    return "\n".join(lines)

def update_index_gist(s: Session, gist_id: str, target_md: str, content_md: str) -> str:
    payload = {
        "description": "Auto-generated index of my PUBLIC gists",
        "files": { target_md: {"content": content_md} },
    }
    r = _req_with_retry(s, "PATCH", f"{API}/gists/{gist_id}", json=payload)
    if r.status_code == 404:
        print("INDEX_GIST_ID not found or token lacks access to that gist.", file=sys.stderr)
        sys.exit(4)
    r.raise_for_status()
    return r.json().get("html_url", "(unknown)")

def main() -> int:
    cfg = load_cfg()
    s = make_session(cfg.token)
    gists = list_public_gists(s, cfg.username)
    md = build_markdown(gists)

    # Always print Markdown to stdout
    print(md)

    # Optionally update gist if both envs are present
    if cfg.index_gist_id and cfg.token:
        try:
            url = update_index_gist(s, cfg.index_gist_id, cfg.target_md, md)
            print(f"\n[info] Updated gist: {url}", file=sys.stderr)
        except requests.HTTPError as e:
            status = getattr(e, "response", None).status_code if getattr(e, "response", None) else "HTTP"
            print(f"[warn] Gist update failed ({status}): {e}", file=sys.stderr)
            return 5
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Unhandled error: {e!r}", file=sys.stderr)
        sys.exit(6)
