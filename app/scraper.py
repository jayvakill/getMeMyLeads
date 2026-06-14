import io
import re
import time
import random
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote, quote_plus
from bs4 import BeautifulSoup

# Rotate user-agents to reduce the chance of being fingerprinted as a bot.
# Bing News RSS is the most sensitive; TechCrunch and YC are generally open.
USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

JOB_BOARD_DOMAINS = {
    'boards.greenhouse.io': 'Greenhouse',
    'jobs.lever.co': 'Lever',
    'jobs.ashbyhq.com': 'Ashby',
    'apply.workable.com': 'Workable',
}

FUNDING_NEWS_DOMAINS = {
    'techcrunch.com': 'TechCrunch',
    'businesswire.com': 'Business Wire',
    'prnewswire.com': 'PR Newswire',
    'venturebeat.com': 'VentureBeat',
    'crunchbase.com': 'Crunchbase',
}

# Map YC batch letters/years to approximate stage
def _batch_to_stage(batch):
    if not batch:
        return 'Seed'
    year_match = re.search(r'(\d{2,4})', batch)
    if year_match:
        year = int(year_match.group(1))
        if year < 100:
            year += 2000
        if year >= 2023:
            return 'Seed'
        if year >= 2020:
            return 'Series A'
        return 'Series B+'
    return 'Seed'


class Scraper:
    def __init__(self, logger):
        self.logger = logger
        self.stats = {
            'pages_scraped': 0,
            'failed_urls': [],
            'blocked_sources': [],
        }

    def _headers(self, accept_xml=False):
        h = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        if accept_xml:
            h['Accept'] = 'application/rss+xml, application/xml, text/xml, */*'
        else:
            h['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        return h

    def _sleep(self, lo=1.5, hi=4.0):
        # Random delay between requests to stay under rate-limit thresholds.
        time.sleep(random.uniform(lo, hi))

    def get_page(self, url, timeout=30, delay=True, json=False):
        if delay:
            self._sleep()
        try:
            resp = requests.get(url, headers=self._headers(), timeout=timeout)
            if resp.status_code in (403, 429, 503):
                self.logger.warning(f"Blocked ({resp.status_code}): {url[:80]}")
                self.stats['blocked_sources'].append(url)
                return None
            resp.raise_for_status()
            self.stats['pages_scraped'] += 1
            return resp.json() if json else resp.text
        except requests.RequestException as e:
            self.logger.error(f"Failed {url[:80]}: {e}")
            self.stats['failed_urls'].append(url)
            return None

    # ------------------------------------------------------------------ #
    # TechCrunch RSS
    # ------------------------------------------------------------------ #
    def scrape_techcrunch_rss(self):
        url = "https://techcrunch.com/feed/"
        try:
            self._sleep(1, 2)
            resp = requests.get(url, headers=self._headers(accept_xml=True), timeout=30)
            resp.raise_for_status()
            root = ET.parse(io.StringIO(resp.text)).getroot()
            channel = root.find('channel')
            if channel is None:
                return []
            kw = {'raises', 'seed', 'series a', 'series b', 'funding', 'million', 'billion', 'round', 'invest'}
            results = []
            for item in channel.findall('item'):
                title = (item.findtext('title') or '').strip()
                description = re.sub(r'<[^>]+>', ' ', item.findtext('description') or '')
                link = (item.findtext('link') or '').strip()
                pub_date = (item.findtext('pubDate') or '').strip()
                if any(k in title.lower() for k in kw):
                    results.append({
                        'title': title,
                        'snippet': description.strip()[:400],
                        'url': link,
                        'pub_date': pub_date,
                        'source': 'TechCrunch',
                    })
            self.stats['pages_scraped'] += 1
            self.logger.info(f"TechCrunch RSS: {len(results)} funding items")
            return results
        except Exception as e:
            self.logger.error(f"TechCrunch RSS: {e}")
            self.stats['failed_urls'].append(url)
            return []

    # ------------------------------------------------------------------ #
    # Bing News RSS — search engine for funding and hiring queries
    # ------------------------------------------------------------------ #
    def search_bing_news(self, query, max_results=8):
        # Bing News RSS is the workhorse here — it lets us search arbitrary
        # phrases like `raises Series A "B2B SaaS"` without needing an API key.
        url = f"https://www.bing.com/news/search?q={quote_plus(query)}&format=RSS"
        try:
            self._sleep(2, 5)
            resp = requests.get(url, headers=self._headers(accept_xml=True), timeout=30)
            resp.raise_for_status()
            root = ET.parse(io.StringIO(resp.text)).getroot()
            channel = root.find('channel')
            if channel is None:
                return []
            results = []
            for item in channel.findall('item')[:max_results]:
                title = (item.findtext('title') or '').strip()
                link = (item.findtext('link') or '').strip()
                description = (item.findtext('description') or '').strip()
                pub_date = (item.findtext('pubDate') or '').strip()
                # Extract actual URL from Bing redirect
                actual_url = self._unwrap_bing_url(link) or link
                source_name = self._domain_to_source(actual_url)
                if title:
                    results.append({
                        'title': title,
                        'snippet': description[:400],
                        'url': actual_url,
                        'pub_date': pub_date,
                        'source': source_name,
                    })
            self.stats['pages_scraped'] += 1
            self.logger.info(f"Bing News '{query[:50]}': {len(results)} results")
            return results
        except Exception as e:
            self.logger.error(f"Bing News error '{query[:50]}': {e}")
            self.stats['failed_urls'].append(url)
            return []

    def _unwrap_bing_url(self, link):
        # Bing wraps the real URL in a redirect; pull the actual destination out.
        m = re.search(r'[&?]url=([^&]+)', link)
        if m:
            return unquote(m.group(1))
        return link

    def _domain_to_source(self, url):
        domain = re.sub(r'^www\.', '', urlparse(url).netloc)
        return FUNDING_NEWS_DOMAINS.get(domain, JOB_BOARD_DOMAINS.get(domain, domain))

    # ------------------------------------------------------------------ #
    # YC Work at a Startup API — best source for startup hiring signals
    # ------------------------------------------------------------------ #
    def scrape_yc_jobs(self, query, count=20):
        # Work at a Startup has an undocumented JSON search endpoint that returns
        # structured job data including company batch (W24, S23, etc.) which we
        # convert to a stage estimate. No auth required.
        url = f"https://www.workatastartup.com/jobs/search?q={quote_plus(query)}&page=1&count={count}"
        try:
            self._sleep(1, 3)
            resp = requests.get(url, headers={**self._headers(), 'Accept': 'application/json'}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get('jobs', [])
            results = []
            for job in jobs:
                stage = _batch_to_stage(job.get('companyBatch', ''))
                company_slug = job.get('companySlug', '')
                job_id = job.get('id', '')
                job_url = f"https://www.workatastartup.com/jobs/{job_id}" if job_id else ''
                results.append({
                    'job_title': job.get('title', ''),
                    'company': job.get('companyName', ''),
                    'description': job.get('companyOneLiner', ''),
                    'location': job.get('location', ''),
                    'stage': stage,
                    'url': job_url,
                    'company_slug': company_slug,
                    'yc_batch': job.get('companyBatch', ''),
                    'source': 'YC Work at a Startup',
                })
            self.stats['pages_scraped'] += 1
            self.logger.info(f"YC Jobs '{query}': {len(results)} listings")
            return results
        except Exception as e:
            self.logger.error(f"YC Jobs error '{query}': {e}")
            self.stats['failed_urls'].append(url)
            return []

    # ------------------------------------------------------------------ #
    # Hacker News Jobs page
    # ------------------------------------------------------------------ #
    def scrape_hn_jobs(self):
        url = "https://news.ycombinator.com/jobs"
        html = self.get_page(url, delay=True)
        if not html:
            return []
        soup = BeautifulSoup(html, 'lxml')
        results = []
        for row in soup.select('.athing'):
            title_el = row.select_one('.titleline a, .title a')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get('href', '')
            if href and not href.startswith('http'):
                href = 'https://news.ycombinator.com/' + href.lstrip('/')
            results.append({'title': title, 'url': href, 'snippet': title, 'source': 'Hacker News Jobs'})
        self.logger.info(f"HN Jobs: {len(results)} listings")
        return results

    # ------------------------------------------------------------------ #
    # Remote OK public API
    # ------------------------------------------------------------------ #
    def scrape_remoteok(self):
        url = "https://remoteok.com/api"
        try:
            self._sleep(1, 2)
            resp = requests.get(url, headers={'User-Agent': random.choice(USER_AGENTS)}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            jobs = [j for j in data if isinstance(j, dict) and j.get('position')]
            self.stats['pages_scraped'] += 1
            self.logger.info(f"Remote OK: {len(jobs)} total jobs")
            return jobs
        except Exception as e:
            self.logger.error(f"Remote OK: {e}")
            self.stats['failed_urls'].append(url)
            return []

    # ------------------------------------------------------------------ #
    # Scrape a job listing page (Greenhouse / Lever / Ashby)
    # ------------------------------------------------------------------ #
    def scrape_job_page(self, url):
        html = self.get_page(url)
        if not html:
            return None
        soup = BeautifulSoup(html, 'lxml')

        job_title = self._extract_first(soup, [
            'h1.app-title', 'h1.job-title', '.posting-headline h2',
            '.job-post-title', 'h1',
        ])
        company = self._extract_first(soup, ['meta[property="og:site_name"]'], attr='content')
        if not company:
            company = self._extract_first(soup, ['.company-name', '.employer-name', '.posting-company'])
        location = self._extract_first(soup, [
            '.location', '.posting-location', '.job-location', '.location--job'
        ])
        description = ''
        for sel in ['.content', '#content', '.job-description', '.posting-description', 'article']:
            el = soup.select_one(sel)
            if el:
                description = el.get_text(separator=' ', strip=True)[:1500]
                break

        if not job_title:
            return None

        domain = re.sub(r'^www\.', '', urlparse(url).netloc)
        source_name = JOB_BOARD_DOMAINS.get(domain, domain)
        return {
            'job_title': job_title,
            'company': company or '',
            'description': description,
            'location': location or '',
            'url': url,
            'source': source_name,
        }

    # ------------------------------------------------------------------ #
    # Scrape a news article for full text
    # ------------------------------------------------------------------ #
    def scrape_article(self, url):
        html = self.get_page(url)
        if not html:
            return None
        soup = BeautifulSoup(html, 'lxml')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()

        title = self._extract_first(soup, ['meta[property="og:title"]'], attr='content')
        if not title:
            title = self._extract_first(soup, ['h1', 'title'])

        content = ''
        for sel in ['article', '.article-content', '.post-content', '.entry-content', 'main', '#content']:
            el = soup.select_one(sel)
            if el:
                content = el.get_text(separator=' ', strip=True)[:3000]
                break
        if not content:
            content = soup.get_text(separator=' ', strip=True)[:3000]

        domain = re.sub(r'^www\.', '', urlparse(url).netloc)
        return {
            'title': title or '',
            'content': content,
            'url': url,
            'source': FUNDING_NEWS_DOMAINS.get(domain, domain),
        }

    # ------------------------------------------------------------------ #
    def _extract_first(self, soup, selectors, attr=None):
        for sel in selectors:
            el = soup.select_one(sel)
            if not el:
                continue
            val = el.get(attr, '').strip() if attr else el.get_text(strip=True)
            if val:
                return val
        return ''

    def classify_url(self, url):
        if not url:
            return 'unknown'
        domain = re.sub(r'^www\.', '', urlparse(url).netloc)
        if domain in JOB_BOARD_DOMAINS:
            return 'job'
        if domain in FUNDING_NEWS_DOMAINS:
            return 'article'
        return 'unknown'
