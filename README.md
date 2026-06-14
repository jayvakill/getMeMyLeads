# getMeMyLeads

Autonomous lead generation engine for freelance content and marketing consultants. Scrapes 5 public sources daily to surface B2B tech startups that have recently raised funding or are actively hiring for content/marketing roles.

No API keys required. No sales automation. Output is a scored, deduplicated CSV you open in a spreadsheet.

## How it works

Each run:
1. Scrapes TechCrunch RSS, Bing News RSS, YC Work at a Startup, Hacker News Jobs, and Remote OK
2. Extracts company name, funding amount, stage, job title, and relevant person
3. Filters to B2B tech only (rejects consumer/lifestyle companies)
4. Deduplicates by domain and normalized company name
5. Scores each lead 0–130 (Seed/Series A with content hiring = highest)
6. Marks each row `priority_tier = High | Low`
7. Exports a sorted CSV to `data/exports/startup_signal_dump_YYYY-MM-DD.csv`

## Quick start

```bash
cd /home/yourmom/getMeMyLeads
python3 app/main.py
```

Output: `data/exports/startup_signal_dump_2026-06-13.csv`
Log: `data/logs/run_2026-06-13.log`

## Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

Install system-wide (no venv needed, stdlib + these three packages):

```bash
pip install requests beautifulsoup4 lxml
```

## Scheduling with cron

Run once daily at 7 AM:

```bash
crontab -e
```

Add this line:

```
0 7 * * * cd /home/yourmom/getMeMyLeads && python3 app/main.py >> data/logs/cron.log 2>&1
```

### Scheduling with systemd (alternative)

Create `/etc/systemd/system/getmymyleads.service`:

```ini
[Unit]
Description=getMeMyLeads daily lead scrape
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=yourmom
WorkingDirectory=/home/yourmom/getMeMyLeads
ExecStart=/usr/bin/python3 app/main.py
StandardOutput=append:/home/yourmom/getMeMyLeads/data/logs/systemd.log
StandardError=append:/home/yourmom/getMeMyLeads/data/logs/systemd.log
```

Create `/etc/systemd/system/getmymyleads.timer`:

```ini
[Unit]
Description=Run getMeMyLeads daily at 7 AM

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now getmymyleads.timer
sudo systemctl status getmymyleads.timer
```

Check logs:

```bash
journalctl -u getmymyleads.service -f
tail -f data/logs/run_$(date +%Y-%m-%d).log
```

## Output CSV fields

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

data/
  startup_signals.db    — SQLite (persists across runs)
  exports/              — daily CSVs
  logs/                 — daily logs
```
