# Gist Index (Public)

This repo hosts a tiny script + workflow that builds an index of **public** gists for a username and overwrites a designated “index” gist with a Markdown table.

See the resulting Gist here: https://gist.github.com/RichLewis007/a48c0ac6b651a36724ce6314d5242c74

## Setup

1. Create (or choose) the gist that will serve as your index.
   - Copy its **Gist ID** (the alphanumeric slug in the URL) – set it as the secret `INDEX_GIST_ID`.

2. Create a token with **gist** read/write:
   - Fine-grained or classic is fine; minimum permission is “gist”.
   - Save it as the secret `GIST_TOKEN`.

3. (Optional) Change the username:
   - In the workflow, set `GITHUB_USERNAME` to your handle (defaults to `RichLewis007` here).

4. Commit and push. The workflow:
   - Runs daily at **13:00 UTC** (≈ 9:00 AM ET).
   - Can be run on demand via **Actions → Run workflow**.

## Manual “force update” (CLI)

If you want to regenerate immediately without waiting for the cron:

```bash
# From this repo root
export GITHUB_USERNAME="RichLewis007"
export INDEX_GIST_ID="YOUR_INDEX_GIST_ID"
export GITHUB_TOKEN="YOUR_TOKEN_WITH_GIST_SCOPE"
python3 gist_index.py
