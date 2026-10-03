# Job Hunter (Kassel)

Collects Werkstudent, internship and mini-job postings, scores them against your
field (SDR, DSP, RF, drones, Python, C++ ...), flags German-language requirements,
and shows everything on a dashboard. Optional Telegram alerts for new matches.

## 1. Run it on your Mac in VS Code (5 min)

```bash
cd job-hunter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python hunter.py                      # fetches jobs -> docs/jobs.json
python -m http.server 8000 -d docs    # then open http://localhost:8000
```
(Or use the VS Code "Live Server" extension on `docs/index.html`.)

Edit `config.yaml` to change location, radius, keywords and searches.

## 2. Make it run 24/7 for free (GitHub Actions + Pages)

1. Create a **private or public** GitHub repo and push this folder:
   `git init && git add . && git commit -m "init" && git branch -M main`
   `git remote add origin <your-repo-url> && git push -u origin main`
2. Repo → **Settings → Actions → General → Workflow permissions** → *Read and write*.
3. Repo → **Settings → Pages** → Source: *Deploy from a branch*, branch `main`, folder `/docs`.
   (Pages on a private repo needs a paid plan; use a public repo or just run locally.)
4. Repo → **Actions → Job Hunter → Run workflow** once. After that it runs every 6 hours.
5. Your dashboard: `https://<your-username>.github.io/<repo>/`

## 3. Phone alerts via Telegram (optional)

1. In Telegram, message **@BotFather** → `/newbot` → copy the token.
2. Send any message to your new bot, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `"chat":{"id": ...}`.
3. Repo → **Settings → Secrets and variables → Actions** → add
   `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`.

Locally: `TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=... python hunter.py`

## 4. More sources (v2)

- **Adzuna** (free, ~1000 calls/month): sign up at https://developer.adzuna.com, then set
  `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` (locally as env vars, on GitHub as Actions secrets).
- **Employer career feeds**: add companies to `companies.yaml` (Greenhouse, Lever, Personio or
  SmartRecruiters). The file explains how to spot which one a company uses.
- **Search everywhere** tab on the dashboard: one-click pre-filled searches for LinkedIn, Indeed,
  StepStone, Xing, Google Jobs, student/research sites (jobvector, Absolventa, EURAXESS, Uni Kassel HiWi ...)
  and employers (KNDS, Rheinmetall, Hensoldt ...). Change the list in `docs/index.html`.

## Notes

- Auto-tracked: Bundesagentur für Arbeit, Arbeitnow, Adzuna, employer feeds.
  LinkedIn, Indeed, StepStone and Xing forbid scraping, so use the Search everywhere tab and their email alerts.
- The Bundesagentur list gives only titles, so the language badge there is a guess
  from the title. Open the posting to confirm.
- Save / Applied / Hide are stored in your browser only.
- To add a source, write a `fetch_xyz()` that returns job dicts like the others
  and add it to `SOURCES` in `hunter.py`.
