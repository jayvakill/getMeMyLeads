# PROJECT_OUTCOMES.md — getMeMyLeads

## Project Summary

Autonomous daily lead generation engine for freelance content/marketing consultants. Scrapes 5 public sources (TechCrunch RSS, Bing News RSS, YC Work at a Startup, Hacker News Jobs, Remote OK) to find B2B tech startups that have recently raised funding or are actively hiring content/marketing roles. Deduplicates by domain and company name, scores each lead 0–130, marks High/Low priority, and exports a sorted CSV. No API keys, no email enrichment, no outreach automation.

---

## Requirements Checklist

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Category normalization: AI/Ai/ai → "AI" consistently | **Completed** |
| 2 | Seed and Series A prioritized; Pre-Seed and B+ marked Low | **Completed** |
| 3 | Unknown stage companies in raw dump, not High unless strong signals | **Completed** |
| 4 | CSV includes all 17 required fields (inc. priority_tier) | **Completed** |
| 5 | Every row has source_url and context_summary | **Completed** (1 known exception, see Gaps) |
| 6 | Cron setup instructions in README.md | **Completed** |
| 7 | PROJECT_OUTCOMES.md in required format | **Completed** |
| 8 | Re-run after fixes, results documented | **Completed** |

---

## Output Validation

**Run date:** 2026-06-13  
**Runtime:** 365 seconds (~6 minutes)  
**Pages scraped:** 108  

### Record counts

| Metric | Value |
|--------|-------|
| Raw records extracted | 143 |
| After deduplication | 116 |
| Saved to SQLite | 116 |
| Exported to CSV | 116 |

### Signal breakdown

| Signal type | Count |
|------------|-------|
| Funding | 55 |
| Hiring | 61 |

### Stage breakdown

| Stage | Count | Avg score | Priority tier |
|-------|-------|-----------|---------------|
| Seed | 48 | 81 | High (if score ≥ 70) |
| Series A | 44 | 78 | High (if score ≥ 70) |
| Pre-Seed | 3 | 70 | Low (all) |
| Series B | 2 | 50 | Low (all) |
| Series B+ | 11 | 27 | Low (all) |
| Unknown | 8 | 48 | Low (all) |

### Priority tier split

| Tier | Count | Criteria |
|------|-------|---------|
| High | 78 | Seed or Series A AND score ≥ 70 |
| Low | 38 | Pre-Seed, Series B/B+, unknown stage, or score < 70 |

### Category normalization

All AI variants resolve to `"AI"`. No `"Ai"` or `"ai"` entries in output.

| Category | Count |
|----------|-------|
| AI | 67 |
| (blank) | 23 |
| Cybersecurity | 11 |
| Fintech | 4 |
| Data | 3 |
| SaaS | 2 |
| DevOps | 2 |
| API | 2 |
| Cloud | 1 |
| Automation | 1 |

### CSV field completeness

| Field | Missing rows |
|-------|-------------|
| source_url | 0 |
| context_summary | 0 |
| company_name | 1 (see Gaps) |
| All other required fields | 0 |

### Source reliability

| Source | Result |
|--------|--------|
| TechCrunch RSS | 2 funding items |
| Bing News RSS (18 queries) | 64 articles |
| YC Work at a Startup | 22–29 listings per query |
| Hacker News Jobs | 30 listings |
| Remote OK API | 100 total (filtered by role) |
| Blocked (403) | 3 URLs (datacenterdynamics.com — expected) |
| Failed (404) | 1 URL (Yahoo Finance stale link — expected) |

---

## Test Results

| Test | Result |
|------|--------|
| `python3 app/main.py` runs to completion | PASS |
| All 116 records saved to SQLite | PASS |
| CSV exports 116 rows with 17 fields | PASS |
| No "Ai" or "ai" in category column | PASS |
| Pre-Seed not in High tier | PASS |
| Series B/B+ not in High tier | PASS |
| Unknown stage not in High tier | PASS |
| All rows have source_url | PASS (116/116) |
| All rows have context_summary | PASS (116/116) |
| High tier contains only Seed/Series A rows | PASS |
| CSV sorted: High tier first, then by score desc | PASS |

---

## Gaps or Missing Items

### 1 row with blank company_name (known)
- **Row:** index 98, source `betakit.com`
- **URL:** `https://betakit.com/motion-closes-30-million-usd-series-b-in-bid-to-become-command-centre-for-creative-strategists/`
- **Why:** The article headline starts with a lowercase "motion" rather than a headline-case company name, so the regex `^([A-Z][A-Za-z0-9...])` doesn't match. Company is "Motion" (Series B project management tool).
- **Impact:** Row is included in the raw dump as `priority_tier = Low` (Series B, score 50). Does not affect High-priority output.
- **Fix if needed:** Add a fallback that extracts company name from the article slug/URL path.

### 23 rows with blank category (known)
- Companies where neither the `category_keywords` dict nor the `categories.txt` taxonomy matched any keyword in the scraped text.
- Primarily YC job listings with minimal company descriptions (one-liner only).
- These rows are still valid leads; they simply lack category enrichment. All are `priority_tier = Low`.

### Bing blocking (expected, non-critical)
- 3 URLs from `datacenterdynamics.com` return 403 on every run. These are consistently the same URLs appearing in Bing results. The companies themselves were captured from the Bing News headline/snippet without needing to load the full article.

---

## Known Issues

| Issue | Severity | Status |
|-------|----------|--------|
| `'pre-seed'` was in `SEED_STAGES` causing Pre-Seed to score as high as Seed | High | **Fixed** — Pre-Seed now gets +10 (not +30); all Pre-Seed rows are `Low` |
| `_load_categories()` lowercased config file entries; `.title()` re-cased "ai" → "Ai" | High | **Fixed** — config file case preserved; fallback loop now returns original case |
| 1 row with blank company_name (betakit.com article about Motion) | Low | Documented above; row remains in raw dump as Low priority |
| Yahoo Finance link returns 404 on every run | Low | Stale URL in Bing index; only 1 URL affected, logged and skipped |

---

## Final Assessment

| Dimension | Status |
|-----------|--------|
| Scrapes and extracts real startup signals | **Yes** |
| Category normalization correct | **Yes** |
| Stage-based prioritization correct | **Yes** |
| CSV contains all required fields | **Yes** |
| source_url present on all rows | **Yes** |
| context_summary present on all rows | **Yes** |
| Cron/scheduling documented in README | **Yes** |
| No email enrichment or sales automation | **Yes** |
| Runs reliably end-to-end | **Yes** |

**Overall: Yes** — MVP is complete and validated. All 8 required follow-ups addressed. 116 leads exported with correct priority tiers, normalized categories, and full field completeness (one known blank company_name row, Low priority, documented).
