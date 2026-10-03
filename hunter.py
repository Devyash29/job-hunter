#!/usr/bin/env python3
"""Job Hunter: collects jobs from several sources, scores them against your
field keywords, writes docs/jobs.json (the dashboard reads it) and can send
Telegram alerts for new matches."""
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

ROOT = Path(__file__).parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "jobs.json"
HEADERS = {"User-Agent": "job-hunter/1.0 (personal use)"}
NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    print(msg, flush=True)


# ---------- sources ----------
def _ba_item(it, hint):
    """Parse one Bundesagentur posting (works with the current v6 and the old v4 field names)."""
    if not isinstance(it, dict):
        return None
    ref = it.get("referenznummer") or it.get("refnr")
    if not isinstance(ref, str) or not ref:
        return None
    adr = {}
    locs = it.get("stellenlokationen")
    if isinstance(locs, list) and locs and isinstance(locs[0], dict) and isinstance(locs[0].get("adresse"), dict):
        adr = locs[0]["adresse"]
    elif isinstance(it.get("arbeitsort"), dict):
        adr = it["arbeitsort"]
    place = ", ".join(str(x) for x in [adr.get("plz"), adr.get("ort")] if x)
    period = it.get("veroeffentlichungszeitraum")
    posted = (period.get("von") if isinstance(period, dict) else None) or it.get("aktuelleVeroeffentlichungsdatum") or ""
    title = it.get("stellenangebotsTitel") or it.get("hauptberuf") or it.get("titel") or it.get("beruf") or ""
    company = it.get("firma") or it.get("arbeitgeber") or ""
    return {
        "id": f"ba-{ref}",
        "title": str(title),
        "company": str(company),
        "location": place or "Deutschland",
        "url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/" + quote(ref, safe=""),
        "source": "Bundesagentur",
        "posted": str(posted)[:10],
        "kind_hint": hint,
        "text": str(it.get("hauptberuf") or it.get("beruf") or ""),
    }


def fetch_arbeitsagentur():
    """Official job board of the German Federal Employment Agency (API v6; v4 was retired)."""
    url = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
    headers = {**HEADERS, "X-API-Key": "jobboerse-jobsuche"}
    cutoff = (NOW - timedelta(days=CFG["max_age_days"])).strftime("%Y-%m-%d")
    jobs = []
    for s_ in CFG["searches"]:
        base = {"wo": CFG["location"], "umkreis": CFG["radius_km"], "size": 50, "page": 1}
        if s_.get("what"):
            base["was"] = s_["what"]
        filters = {k: s_[k] for k in ("arbeitszeit", "angebotsart") if s_.get(k)}
        # Try the full query first; if the API rejects a parameter (HTTP 400) fall back step by step.
        attempts = [
            ({**base, **filters, "veroeffentlichtseit": CFG["max_age_days"]}, True),
            ({**base, **filters}, True),
            (base, False),
        ]
        data, hint_ok = None, True
        for params, ok in attempts:
            try:
                r = requests.get(url, params=params, headers=headers, timeout=30)
                if r.status_code == 400:
                    continue
                r.raise_for_status()
                data, hint_ok = r.json(), ok
                break
            except Exception as e:
                log(f"[BA] search '{s_.get('what')}' failed: {e}")
                break
        if not isinstance(data, dict):
            continue
        items = data.get("ergebnisliste") or data.get("stellenangebote") or []
        if not isinstance(items, list):
            items = []
        log(f"[BA] '{s_.get('what') or '(all)'}' -> {len(items)}")
        for it in items:
            try:
                job = _ba_item(it, s_["kind"] if hint_ok else "")
            except Exception as e:
                log(f"[BA] skipped a malformed row: {e}")
                continue
            if job and (not job["posted"] or job["posted"] >= cutoff):
                jobs.append(job)
        time.sleep(0.6)
    return jobs


def fetch_arbeitnow():
    """Arbeitnow public API: many English-language jobs in Germany."""
    city = CFG["location"].lower()
    jobs = []
    for page in range(1, CFG.get("arbeitnow_pages", 3) + 1):
        try:
            r = requests.get("https://www.arbeitnow.com/api/job-board-api",
                             params={"page": page}, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json().get("data", [])
        except Exception as e:
            log(f"[Arbeitnow] page {page} failed: {e}")
            break
        log(f"[Arbeitnow] page {page} -> {len(data)}")
        for it in data:
            loc = it.get("location") or ""
            if city not in loc.lower() and not it.get("remote"):
                continue
            ts = it.get("created_at")
            posted = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else ""
            jobs.append({
                "id": f"an-{it.get('slug')}",
                "title": it.get("title") or "",
                "company": it.get("company_name") or "",
                "location": loc + (" (remote)" if it.get("remote") else ""),
                "url": it.get("url") or "",
                "source": "Arbeitnow",
                "posted": posted,
                "kind_hint": "",
                "text": re.sub(r"<[^>]+>", " ", it.get("description") or "")[:4000],
            })
        time.sleep(0.6)
    return jobs

def fetch_adzuna():
    """Adzuna aggregator (free key: developer.adzuna.com). Needs ADZUNA_APP_ID / ADZUNA_APP_KEY."""
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        log("[Adzuna] no keys set, skipping.")
        return []
    jobs = []
    for q in CFG.get("adzuna_queries", []):
        params = {"app_id": app_id, "app_key": app_key, "what": q, "where": CFG["location"],
                  "distance": CFG["radius_km"], "max_days_old": CFG["max_age_days"],
                  "results_per_page": 50, "sort_by": "date"}
        try:
            r = requests.get("https://api.adzuna.com/v1/api/jobs/de/search/1", params=params,
                             headers=HEADERS, timeout=30)
            r.raise_for_status()
            items = r.json().get("results", [])
        except Exception as e:
            log(f"[Adzuna] '{q}' failed: {e}")
            continue
        log(f"[Adzuna] '{q}' -> {len(items)}")
        for it in items:
            jobs.append({
                "id": f"az-{it.get('id')}",
                "title": it.get("title") or "",
                "company": (it.get("company") or {}).get("display_name", ""),
                "location": (it.get("location") or {}).get("display_name", ""),
                "url": it.get("redirect_url") or "",
                "source": "Adzuna",
                "posted": (it.get("created") or "")[:10],
                "kind_hint": "",
                "text": re.sub(r"<[^>]+>", " ", it.get("description") or "")[:4000],
            })
        time.sleep(0.6)
    return jobs


def _company_jobs(c):
    """Return raw (id, title, location, url, posted) tuples for one company career feed."""
    ats, cid = c["ats"].lower(), c["id"]
    if ats == "greenhouse":
        d = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{cid}/jobs", headers=HEADERS, timeout=30).json()
        for j in d.get("jobs", []):
            yield (j["id"], j["title"], (j.get("location") or {}).get("name", ""), j.get("absolute_url", ""), (j.get("updated_at") or "")[:10])
    elif ats == "lever":
        d = requests.get(f"https://api.lever.co/v0/postings/{cid}", params={"mode": "json"}, headers=HEADERS, timeout=30).json()
        for j in d:
            ts = j.get("createdAt")
            posted = datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%d") if ts else ""
            yield (j["id"], j["text"], (j.get("categories") or {}).get("location", ""), j.get("hostedUrl", ""), posted)
    elif ats == "personio":
        r = requests.get(f"https://{cid}.jobs.personio.de/xml", headers=HEADERS, timeout=30)
        for pos in ET.fromstring(r.content).findall("position"):
            pid = pos.findtext("id")
            yield (pid, pos.findtext("name") or "", pos.findtext("office") or "",
                   f"https://{cid}.jobs.personio.de/job/{pid}", (pos.findtext("createdAt") or "")[:10])
    elif ats == "smartrecruiters":
        d = requests.get(f"https://api.smartrecruiters.com/v1/companies/{cid}/postings", params={"limit": 100}, headers=HEADERS, timeout=30).json()
        for j in d.get("content", []):
            loc = j.get("location") or {}
            yield (j["id"], j["name"], ", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
                   f"https://jobs.smartrecruiters.com/{cid}/{j['id']}", (j.get("releasedDate") or "")[:10])
    else:
        raise ValueError(f"unknown ats '{c['ats']}' (use greenhouse, lever, personio, smartrecruiters)")


def fetch_companies():
    """Watch career feeds of specific employers listed in companies.yaml."""
    path = ROOT / "companies.yaml"
    if not path.exists():
        return []
    companies = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("companies") or []
    loc_re = re.compile(CFG.get("company_location_regex", ".*"), re.I)
    jobs = []
    for c in companies:
        try:
            rows = list(_company_jobs(c))
        except Exception as e:
            log(f"[{c.get('name')}] failed: {e}")
            continue
        kept = 0
        for jid, title, loc, url, posted in rows:
            if loc and not loc_re.search(loc):
                continue
            kept += 1
            jobs.append({"id": f"co-{c['id']}-{jid}", "title": title, "company": c["name"], "location": loc,
                         "url": url, "source": f"{c['name']} careers", "posted": posted,
                         "kind_hint": "", "text": ""})
        log(f"[{c.get('name')}] {len(rows)} postings, {kept} in your region")
        time.sleep(0.5)
    return jobs


SOURCES = [fetch_arbeitsagentur, fetch_arbeitnow, fetch_adzuna, fetch_companies]


# ---------- analysis ----------
def classify(job):
    title = job["title"].lower()
    full = f"{title} {job['text']}".lower()
    if re.search(r"werkstudent|working student|studentenjob|studentische", full):
        return "werkstudent"
    if re.search(r"praktik|\bintern\b|internship", title):
        return "internship"
    if re.search(r"minijob|mini-job|aushilfe|geringfügig", full):
        return "minijob"
    return job.get("kind_hint") or "other"


def score(job):
    text = f"{job['title']} {job['company']} {job['text']}".lower()
    pts = 0
    for kw, weight in CFG["field_keywords"].items():
        if re.search(r"(?<!\w)" + re.escape(kw.lower()), text):
            pts += weight
    return min(pts, 10)


def lang_hint(job):
    if re.search(CFG["german_required_regex"], job["text"].lower()):
        return "de-required"
    words = set(re.findall(r"[a-zäöüß]+", job["title"].lower()))
    de = len(words & set(CFG["german_title_words"]))
    en = len(words & set(CFG["english_title_words"]))
    if de > en:
        return "de"
    return "en" if en else "unknown"


def excluded(job):
    t = job["title"].lower()
    return any(w in t for w in CFG["exclude_words"])


# ---------- notifications ----------
def notify(new_jobs, first_run):
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        log("Telegram not configured, skipping alerts.")
        return
    picks = [j for j in new_jobs if j["lang"] != "de-required"
             and (j["score"] >= CFG["min_notify_score"] or j["kind"] in CFG["notify_kinds"])]
    picks.sort(key=lambda j: j["score"], reverse=True)
    for j in picks[:10 if first_run else 15]:
        text = f"New {j['kind']}: {j['title']}\n{j['company']} | {j['location']}\nMatch {j['score']}/10\n{j['url']}"
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=20)
        except Exception as e:
            log(f"Telegram failed: {e}")
        time.sleep(0.4)
    log(f"Telegram: sent {min(len(picks), 15)} alert(s).")


# ---------- main ----------
def main():
    old = {}
    if OUT.exists():
        try:
            old = {j["id"]: j for j in json.loads(OUT.read_text(encoding="utf-8")).get("jobs", [])}
        except Exception:
            pass
    merged, new_jobs, seen_now = dict(old), [], set()
    for fetch in SOURCES:
        for j in fetch():
            if j["id"] in seen_now or excluded(j):
                continue
            seen_now.add(j["id"])
            j["kind"] = classify(j)
            j["score"] = score(j)
            j["lang"] = lang_hint(j)
            if j["kind"] == "other" and j["score"] == 0:
                continue  # irrelevant
            j.pop("kind_hint", None)
            j["text"] = j["text"][:300]
            if j["id"] in old:
                j["first_seen"] = old[j["id"]].get("first_seen", NOW_ISO)
            else:
                j["first_seen"] = NOW_ISO
                new_jobs.append(j)
            j["last_seen"] = NOW_ISO
            merged[j["id"]] = j
    cutoff = NOW - timedelta(days=CFG["max_age_days"])
    jobs = [j for j in merged.values()
            if datetime.fromisoformat(j["last_seen"].replace("Z", "+00:00")) >= cutoff]
    jobs.sort(key=lambda j: (j["first_seen"], j["score"]), reverse=True)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"updated": NOW_ISO, "jobs": jobs}, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Done: {len(jobs)} jobs total, {len(new_jobs)} new.")
    notify(new_jobs, first_run=not old)


if __name__ == "__main__":
    main()
