# getMeMyLeads — Project Outcomes

## What It Does

Autonomous lead generation engine for freelance content/marketing consultants. Scrapes 5 sources every run to find US/Canada B2B tech startups that have recently raised funding or are actively hiring for content and marketing roles — exactly the companies most likely to need an outside content expert.

## Architecture

```
getMeMyLeads/
├── app/
│   ├── main.py          # Orchestrator — runs all sources end to end
│   ├── scraper.py       # 5-source scraper (TechCrunch, Bing News, YC, HN, RemoteOK)
│   ├── extractor.py     # Company name, funding amount, person, date extraction
│   ├── classifier.py    # Stage detection, category classification, job title matching
│   ├── scoring.py       # Lead quality scoring (0–130 scale)
│   ├── dedupe.py        # Domain + name normalisation and merge
│   ├── database.py      # SQLite persistence (startup_signals table)
│   ├── exporter.py      # CSV export sorted by score
│   └── logger.py        # Rotating daily log file + console
├── config/
│   ├── funding_queries.txt   # 18 Bing News search queries for funding signals
│   ├── hiring_queries.txt    # 16 Bing News queries for hiring signals
│   ├── job_titles.txt        # 20 content/marketing role titles to match
│   └── categories.txt        # B2B tech category taxonomy
└── data/
    ├── startup_signals.db    # SQLite — persists across runs, deduplicates
    ├── exports/              # Daily CSVs: startup_signal_dump_YYYY-MM-DD.csv
    └── logs/                 # Daily log files: run_YYYY-MM-DD.log
```

## Data Sources

| Source | Type | Signal |
|--------|------|--------|
| TechCrunch RSS | Funding news | Companies announcing rounds |
| Bing News RSS (18 queries) | Funding news | Seed/Series A announcements |
| YC Work at a Startup API | Job listings | YC-backed startups hiring content/marketing |
| Hacker News Jobs | Job listings | Tech startups hiring content roles |
| Remote OK API | Job listings | Remote content/marketing roles at startups |

## Run Results (2026-06-13)

```
Runtime:        366 seconds (~6 minutes)
Pages scraped:  107
Raw records:    145
After dedupe:   118 unique companies
Saved to DB:    118
Exported:       118 rows → data/exports/startup_signal_dump_2026-06-13.csv

Signal breakdown:
  Funding signals:  55 companies
  Hiring signals:   63 companies

Stage breakdown:
  Seed:      49  (ideal — pre-revenue growth phase)
  Series A:  45  (strong — scaling marketing)
  Series B+: 13
  Unknown:    8  (missing stage context)
  Pre-Seed:   3

Category breakdown:
  AI:           68
  Cybersecurity: 11
  Fintech:        5
  Data:           3
  DevOps:         2
  SaaS:           2
  Other:         27

Score distribution:
  Score ≥ 80:  83 leads  (70% of total — high quality)
  Score avg:   73 / 130 max
  Score max:   90
```

## Scoring Model

Each lead is scored 0–130:

| Signal | Points |
|--------|--------|
| Seed or Series A stage | +30 |
| Funding amount or date present | +30 |
| Content/marketing job title match | +30 |
| B2B tech category | +20 |
| Both funding and hiring signals | +40 |
| Named founder/executive found | +10 |

Leads scoring 80+ are considered high-priority.

## Sample Top Leads (score = 90)

| Company | Stage | Signal | Amount |
|---------|-------|--------|--------|
| Rivvun AI | Seed | Funding | $7.55M |
| Nudge Security | Series A | Funding | $22.5M |
| Aryon Security | Series A | Funding | $29M |
| Zenskar | Series A | Funding | $15M |
| SRE.ai | Seed | Funding | $7.2M |
| Juicebox | Seed | Hiring | — (Marketing Manager) |
| Retell AI | — | Hiring | — (Marketing Manager) |
| Flagright | — | Hiring | — (Content Lead) |

## How to Run

```bash
cd /home/yourmom/getMeMyLeads
python3 app/main.py
```

Output CSV: `data/exports/startup_signal_dump_YYYY-MM-DD.csv`
Log: `data/logs/run_YYYY-MM-DD.log`

## Dependencies

- Python 3 stdlib
- `requests` — HTTP
- `beautifulsoup4` + `lxml` — HTML parsing

No API keys required. All sources are public.

## Known Limitations

- Some news sites (datacenterdynamics.com, moneycontrol.com) block scrapers (403) — this is expected and logged
- YC Jobs API returns 20–29 listings per search term regardless of query specificity; deduplication handles overlap
- No funding date for hiring-only leads
- Category classifier may tag the same company twice as "AI" and "Ai" due to case normalization gap
