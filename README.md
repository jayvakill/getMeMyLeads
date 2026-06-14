# getMeMyLeads

Autonomous lead generation engine for freelance content and marketing consultants. Scrapes 5 public sources daily to surface B2B tech startups that have recently raised funding or are actively hiring for content/marketing roles.

No API keys required. No sales automation. Output is a scored, deduplicated CSV you open in a spreadsheet.

---

## How it works

Each run:
1. Scrapes TechCrunch RSS, Bing News RSS, YC Work at a Startup, Hacker News Jobs, and Remote OK
2. Extracts company name, funding amount, stage, job title, and relevant person
3. Filters to B2B tech only (rejects consumer/lifestyle companies)
4. Deduplicates by domain and normalized company name
5. Scores each lead 0–130 (Seed/Series A with content hiring = highest)
6. Marks each row `priority_tier = High | Low`
7. Exports to `data/exports/startup_signal_dump_YYYY-MM-DD.csv`
8. Copies to `results/startup_signal_dump_YYYY-MM-DD.csv` and pushes to GitHub

---

## Quick start (manual run)

```bash
cd /home/yourmom/getMeMyLeads
bash scripts/run_daily.sh
```

This runs the scraper, writes today's CSV to `results/`, commits it, and pushes to GitHub.

To run the scraper only (no git push):

```bash
python3 app/main.py
```

---

## Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

Install system-wide (no venv needed — stdlib + these three packages):

```bash
pip install requests beautifulsoup4 lxml
```

---

## Setting up the systemd timer (recommended)

The systemd timer runs `scripts/run_daily.sh` at 7:00 AM every day. If the machine was off at 7 AM, it catches up as soon as it boots (`Persistent=true`).

### Install

```bash
sudo cp deployment/getmymyleads.service /etc/systemd/system/
sudo cp deployment/getmymyleads.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable getmymyleads.timer
sudo systemctl start getmymyleads.timer
```

### Verify the timer is scheduled

```bash
systemctl list-timers | grep getmymyleads
sudo systemctl status getmymyleads.timer
```

### View logs

```bash
# Live output from the most recent run
sudo journalctl -u getmymyleads.service -n 100 --no-pager

# File-based log for today's run
tail -f data/logs/daily_runner_$(date +%Y-%m-%d).log

# Scraper log (detailed per-source output)
tail -f data/logs/run_$(date +%Y-%m-%d).log
```

### Manually trigger the job

```bash
sudo systemctl start getmymyleads.service
```

### Stop or disable

```bash
sudo systemctl disable getmymyleads.timer
sudo systemctl stop getmymyleads.timer
```

---

## Scheduling with cron (alternative)

```bash
crontab -e
```

Add:

```
0 7 * * * cd /home/yourmom/getMeMyLeads && bash scripts/run_daily.sh >> data/logs/cron.log 2>&1
```

---

## Output

Daily results are committed to:

```
results/startup_signal_dump_YYYY-MM-DD.csv
```

Each run produces a new file named by date. Previous files are never overwritten.

Internal working files:

```
data/exports/startup_signal_dump_YYYY-MM-DD.csv   ← scraper output
data/logs/run_YYYY-MM-DD.log                       ← scraper log
data/logs/daily_runner_YYYY-MM-DD.log             ← runner log
data/startup_signals.db                            ← SQLite (not committed)
```

---

## CSV fields

| Field | Description |
|-------|-------------|
| `company_name` | Extracted company name |
| `website` | Company domain (when available) |
| `category` | B2B tech vertical (AI, SaaS, Cybersecurity, etc.) |
| `stage` | Funding stage (Seed, Series A, etc.) |
| `signal_type` | `funding`, `hiring`, or `hiring_and_funding` |
| `signal_details` | Raw headline or job title string |
| `job_title` | Normalized content/marketing role matched |
| `funding_amount` | Amount raised (e.g. $5M) |
| `funding_date` | Date of funding announcement |
| `relevant_person_name` | Named CEO/founder when extractable |
| `relevant_person_title` | Their title |
| `source_name` | TechCrunch, YC Work at a Startup, etc. |
| `source_url` | Direct link to the article or job listing |
| `context_summary` | 1–2 sentence human-readable summary |
| `score` | 0–130 lead quality score |
| `date_found` | Date this record was first scraped |
| `priority_tier` | `High` (Seed/Series A, score ≥ 70) or `Low` |

---

## Scoring model

| Signal | Points |
|--------|--------|
| Seed or Series A stage | +30 |
| Funding amount or date present | +30 |
| Content/marketing job title match | +30 |
| B2B tech category | +20 |
| Both funding and hiring signals | +40 |
| Named founder/exec found | +10 |
| Pre-Seed stage | +10 (reduced — pre-revenue) |
| Series B or B+ stage | −10 (likely have in-house teams) |

`High` priority = Seed or Series A AND score ≥ 70. Everything else is `Low`.

---

## Project structure

```
app/
  main.py        — orchestrator
  scraper.py     — 5-source scraper
  extractor.py   — company/funding/person extraction
  classifier.py  — stage detection, category classification
  scoring.py     — lead quality scoring
  dedupe.py      — domain + name deduplication and merge
  database.py    — SQLite persistence
  exporter.py    — CSV export with priority_tier
  logger.py      — daily rotating log file

config/
  funding_queries.txt   — 18 Bing News search queries
  hiring_queries.txt    — 16 Bing News queries
  job_titles.txt        — 20 content/marketing role titles
  categories.txt        — B2B tech category taxonomy

scripts/
  run_daily.sh   — daily runner: scrape → results/ → git commit → push

deployment/
  getmymyleads.service  — systemd service unit
  getmymyleads.timer    — systemd timer (7 AM daily)

results/
  startup_signal_dump_YYYY-MM-DD.csv   ← committed to GitHub daily

data/
  startup_signals.db    — SQLite (not committed)
  exports/              — internal working copies
  logs/                 — runner and scraper logs
```
