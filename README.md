# Gist Index Automation

[![Update Gist Index](https://github.com/RichLewis007/gist-index/actions/workflows/update-gist-index.yml/badge.svg)](https://github.com/RichLewis007/gist-index/actions/workflows/update-gist-index.yml)

This repo hosts the script and workflow that:
- Builds a Markdown index of my **public gists**
- Updates a designated gist: https://gist.github.com/RichLewis007/a48c0ac6b651a36724ce6314d5242c74
- Commits a copy into the `Public-Gists-from-Rich-Lewis` repo daily

It uses a GitHub Action which runs the Python script on a schedule or manually.

## Setup

1. Create (or choose) the gist that will serve as your index.
   - Copy its **Gist ID** (the alphanumeric slug in the URL) – set it as the secret `INDEX_GIST_ID`.

2. Create a token with **gist** read/write:
   - Fine-grained or classic is fine; minimum permission is “gist”.
   - Save it as the secret `GIST_TOKEN`.

3. (Optional) Change the username:
   - In the workflow, set `GITHUB_USERNAME` to your handle.

4. Commit and push. The workflow:
   - Runs daily at **13:00 UTC** (≈ 9:00 AM ET).
   - Can be run on demand on GitHub site via **Actions → Run workflow**.

## Manual “force update” (CLI)

If you want to regenerate immediately without waiting for the cron:

```bash
# From this repo root
export GITHUB_USERNAME="YOUR_USERNAME"
export INDEX_GIST_ID="YOUR_INDEX_GIST_ID"
export GITHUB_TOKEN="YOUR_TOKEN_WITH_GIST_SCOPE"
uv run --with requests python gist-index.py
```
