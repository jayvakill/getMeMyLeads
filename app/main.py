import os
import sys
import re
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logger import setup_logger
from app.database import init_db, insert_signal, get_by_domain, get_by_name, get_signals_for_date
from app.scraper import Scraper
from app.extractor import build_record_from_article, build_record_from_job, generate_context_summary
from app.classifier import detect_stage, classify_category, detect_job_title_match, is_b2b_tech
from app.scoring import score_company
from app.dedupe import deduplicate, normalize_domain
from app.exporter import export_to_csv

CONFIG_DIR = "config"
LOG_DIR = "data/logs"

CONTENT_ROLE_KEYWORDS = [
    'content marketer', 'head of content', 'content lead', 'social media manager',
    'videographer', 'video editor', 'creative strategist', 'growth marketer',
    'vp growth', 'demand gen', 'marketing manager', 'head of marketing',
    'cmo', 'brand marketing', 'founder brand', 'content marketing',
    'director of content', 'digital marketing',
]


def load_lines(filename):
    path = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [l.strip().strip('"') for l in f if l.strip() and not l.startswith('#')]


def _is_content_role(text):
    t = text.lower()
    return any(kw in t for kw in CONTENT_ROLE_KEYWORDS)


def _extract_company_from_title(title):
    patterns = [
        r'(?:at|@)\s+([A-Z][A-Za-z0-9\s\-]{1,30})',
        r'^([A-Z][A-Za-z0-9\s\-]{1,30})\s+[-–|:]\s+',
        r'^([A-Z][A-Za-z0-9\s\-]{1,30})\s+is\s+hiring',
        r'\(([A-Z][A-Za-z0-9\s\-]{1,30})\)',
    ]
    for pat in patterns:
        m = re.search(pat, title)
        if m:
            name = m.group(1).strip().rstrip(',')
            if 2 < len(name) < 40:
                return name
    return ''


def run():
    logger = setup_logger(LOG_DIR)
    start = time.time()
    today = datetime.now().strftime('%Y-%m-%d')

    logger.info("=" * 60)
    logger.info(f"Daily run started: {today}")
    logger.info("=" * 60)

    init_db()
    scraper = Scraper(logger)

    funding_queries = load_lines('funding_queries.txt')
    hiring_queries = load_lines('hiring_queries.txt')
    job_titles = load_lines('job_titles.txt')

    logger.info(f"Loaded {len(funding_queries)} funding queries, {len(hiring_queries)} hiring queries, "
                f"{len(job_titles)} job titles")

    all_records = []
    extracted = 0
    skipped = 0

    # ------------------------------------------------------------------ #
    # SOURCE 1: TechCrunch RSS
    # ------------------------------------------------------------------ #
    logger.info("--- Source: TechCrunch RSS ---")
    for item in scraper.scrape_techcrunch_rss():
        full_text = ''
        article = scraper.scrape_article(item['url'])
        if article:
            full_text = article.get('content', '')
        rec = build_record_from_article(
            title=item['title'], snippet=item.get('snippet', ''),
            url=item['url'], source_name='TechCrunch',
            pub_date=item.get('pub_date', ''), full_text=full_text,
        )
        if rec and rec.get('company_name'):
            all_records.append(rec)
            extracted += 1
        else:
            skipped += 1

    # ------------------------------------------------------------------ #
    # SOURCE 2: Bing News RSS — funding queries
    # ------------------------------------------------------------------ #
    logger.info("--- Source: Bing News RSS (funding) ---")
    for query in funding_queries:
        for item in scraper.search_bing_news(query, max_results=6):
            full_text = ''
            article = scraper.scrape_article(item['url'])
            if article:
                full_text = article.get('content', '')
            rec = build_record_from_article(
                title=item['title'], snippet=item.get('snippet', ''),
                url=item['url'], source_name=item.get('source', 'Bing News'),
                pub_date=item.get('pub_date', ''), full_text=full_text,
            )
            if rec and rec.get('company_name'):
                all_records.append(rec)
                extracted += 1
            else:
                skipped += 1

    # ------------------------------------------------------------------ #
    # SOURCE 3: YC Work at a Startup — hiring signals
    # ------------------------------------------------------------------ #
    logger.info("--- Source: YC Work at a Startup ---")
    yc_search_terms = [t for t in job_titles if _is_content_role(t)]
    seen_yc_jobs = set()
    for term in yc_search_terms:
        for job in scraper.scrape_yc_jobs(term, count=15):
            uid = (job.get('company', ''), job.get('job_title', ''))
            if uid in seen_yc_jobs:
                continue
            seen_yc_jobs.add(uid)

            stage = job.get('stage', '')
            rec = build_record_from_job(
                job_title=job.get('job_title', ''),
                company_name=job.get('company', ''),
                description=job.get('description', ''),
                url=job.get('url', ''),
                source_name='YC Work at a Startup',
                location=job.get('location', ''),
            )
            if rec:
                if stage and not rec.get('stage'):
                    rec['stage'] = stage
                    rec['context_summary'] = generate_context_summary(rec)
                if job.get('yc_batch'):
                    rec['signal_details'] = (rec.get('signal_details', '') +
                                             f" | YC {job['yc_batch']}")
                all_records.append(rec)
                extracted += 1
            else:
                skipped += 1

    # ------------------------------------------------------------------ #
    # SOURCE 4: Hacker News Jobs
    # ------------------------------------------------------------------ #
    logger.info("--- Source: HN Jobs ---")
    for item in scraper.scrape_hn_jobs():
        title = item.get('title', '')
        if not _is_content_role(title):
            continue
        matched_title = detect_job_title_match(title) or title
        company = _extract_company_from_title(title)
        rec = build_record_from_job(
            job_title=matched_title,
            company_name=company,
            description=item.get('snippet', ''),
            url=item.get('url', ''),
            source_name='Hacker News Jobs',
        )
        if rec:
            all_records.append(rec)
            extracted += 1
        else:
            skipped += 1

    # ------------------------------------------------------------------ #
    # SOURCE 5: Remote OK API
    # ------------------------------------------------------------------ #
    logger.info("--- Source: Remote OK ---")
    remoteok_jobs = scraper.scrape_remoteok()
    for job in remoteok_jobs:
        position = job.get('position', '')
        if not _is_content_role(position):
            continue
        matched_title = detect_job_title_match(position) or position
        company = job.get('company', '')
        description = re.sub(r'<[^>]+>', ' ', job.get('description', ''))[:600]
        rec = build_record_from_job(
            job_title=matched_title,
            company_name=company,
            description=description,
            url=job.get('url', ''),
            source_name='Remote OK',
            location=job.get('location', '') if not job.get('remote') else 'Remote',
        )
        if rec:
            all_records.append(rec)
            extracted += 1
        else:
            skipped += 1

    # ------------------------------------------------------------------ #
    # SOURCE 6: Bing News RSS — hiring queries (news about companies hiring)
    # ------------------------------------------------------------------ #
    logger.info("--- Source: Bing News RSS (hiring) ---")
    for query in hiring_queries[:8]:
        for item in scraper.search_bing_news(query, max_results=4):
            title = item.get('title', '')
            matched_title = detect_job_title_match(title) or detect_job_title_match(item.get('snippet', ''))
            if matched_title:
                company = _extract_company_from_title(title)
                rec = build_record_from_job(
                    job_title=matched_title,
                    company_name=company,
                    description=item.get('snippet', ''),
                    url=item.get('url', ''),
                    source_name=item.get('source', 'Bing News'),
                )
                if rec:
                    all_records.append(rec)
                    extracted += 1
                    continue
            # Try as article (might mention a company hiring)
            rec = build_record_from_article(
                title=title, snippet=item.get('snippet', ''),
                url=item['url'], source_name=item.get('source', 'Bing News'),
                pub_date=item.get('pub_date', ''),
            )
            if rec and rec.get('company_name'):
                all_records.append(rec)
                extracted += 1
            else:
                skipped += 1

    logger.info(f"Raw extracted: {extracted}, skipped: {skipped}")

    # ------------------------------------------------------------------ #
    # Score, deduplicate, re-evaluate signal types
    # ------------------------------------------------------------------ #
    logger.info("--- Scoring & Deduplication ---")
    for rec in all_records:
        rec['score'] = score_company(rec)

    before = len(all_records)
    all_records = deduplicate(all_records)
    removed = before - len(all_records)
    logger.info(f"Dedup: {before} → {len(all_records)} ({removed} removed)")

    # Re-score and refresh summaries after merge
    for rec in all_records:
        rec['score'] = score_company(rec)
        if not rec.get('context_summary') or rec['context_summary'].startswith('This company'):
            rec['context_summary'] = generate_context_summary(rec)

    # ------------------------------------------------------------------ #
    # Save to SQLite
    # ------------------------------------------------------------------ #
    logger.info("--- Saving to SQLite ---")
    saved = 0
    for rec in all_records:
        domain = normalize_domain(rec.get('website', ''))
        existing = get_by_domain(domain) if domain else None
        if not existing:
            existing = get_by_name(rec.get('company_name', ''))
        if not existing:
            insert_signal(rec)
            saved += 1
    logger.info(f"Saved {saved} new records")

    # ------------------------------------------------------------------ #
    # Export CSV
    # ------------------------------------------------------------------ #
    today_records = get_signals_for_date(today)
    if not today_records:
        today_records = all_records

    csv_path, csv_count = export_to_csv(today_records, today)
    logger.info(f"Exported {csv_count} records → {csv_path}")

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"Done in {elapsed:.1f}s | Pages: {scraper.stats['pages_scraped']} | "
                f"Companies: {len(all_records)} | Exported: {csv_count}")
    if scraper.stats['failed_urls']:
        logger.warning(f"Failed ({len(scraper.stats['failed_urls'])}): " +
                       ", ".join(scraper.stats['failed_urls'][:5]))
    if scraper.stats['blocked_sources']:
        logger.warning(f"Blocked ({len(scraper.stats['blocked_sources'])}): " +
                       ", ".join(scraper.stats['blocked_sources'][:5]))
    logger.info("=" * 60)
    return csv_path


if __name__ == '__main__':
    run()
