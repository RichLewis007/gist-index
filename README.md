# Gist Index (Public)

This repo hosts a tiny script + workflow that builds an index of **public** gists for a username and overwrites a designated “index” gist with a Markdown table.

See the resulting Gist here: https://gist.github.com/RichLewis007/a48c0ac6b651a36724ce6314d5242c74

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
