import re
from datetime import datetime
from app.classifier import classify_category, detect_stage, detect_job_title_match, is_b2b_tech

FUNDING_AMOUNT_RE = re.compile(
    r'\$\s*(\d+(?:\.\d+)?)\s*(million|billion|M|B|m|b)',
    re.IGNORECASE
)

# Pattern 1 matches headline format: "Acme AI raises $5M..."
# Pattern 2 matches press-release format: "Acme AI, a B2B SaaS startup..."
COMPANY_NAME_PATTERNS = [
    re.compile(r'^([A-Z][A-Za-z0-9\s\-\.]{1,40}?)\s+(?:raises?|announces?|secures?|closes?|lands?|nabs?|gets?)\b', re.M),
    re.compile(r'^([A-Z][A-Za-z0-9\s\-\.]{1,40}?),\s+(?:a|an|the)\s+\w+\s+startup', re.M | re.I),
]

PERSON_PATTERNS = [
    re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+),?\s+(?:CEO|founder|co-founder|CTO|President|Chief Executive)', re.I),
    re.compile(r'(?:CEO|founder|co-founder|CTO|President)\s+(?:of\s+\w+,?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', re.I),
    re.compile(r'said\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+),?\s+(?:CEO|founder|co-founder|CTO)', re.I),
]

PERSON_TITLE_RE = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+),?\s+(CEO|founder|co-founder|CTO|President|Chief Executive Officer)',
    re.I
)

DATE_PATTERNS = [
    re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', re.I),
    re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
    re.compile(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b', re.I),
]

WEBSITE_RE = re.compile(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)')


def extract_funding_amount(text):
    match = FUNDING_AMOUNT_RE.search(text)
    if not match:
        return ''
    amount, unit = match.group(1), match.group(2).upper()
    if unit in ('M', 'MILLION'):
        return f"${amount}M"
    if unit in ('B', 'BILLION'):
        return f"${amount}B"
    return f"${amount}{unit}"


def extract_company_name(title, text=''):
    for pattern in COMPANY_NAME_PATTERNS:
        m = pattern.search(title)
        if m:
            name = m.group(1).strip().rstrip(',')
            if 2 < len(name) < 50:
                return name
    if title:
        parts = re.split(r'\s+(?:raises?|announces?|secures?|closes?)\s+', title, flags=re.I)
        if len(parts) >= 2 and parts[0]:
            name = parts[0].strip().rstrip(',')
            if 2 < len(name) < 50:
                return name
    return ''


def extract_person(text):
    for pattern in PERSON_PATTERNS:
        m = pattern.search(text)
        if m:
            name = m.group(1).strip()
            if 3 < len(name) < 50:
                return name
    return ''


def extract_person_title(text):
    m = PERSON_TITLE_RE.search(text)
    if m:
        return m.group(2).strip()
    return ''


def extract_funding_date(text, pub_date=''):
    if pub_date:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub_date)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    for pattern in DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            raw = m.group(0)
            for fmt in ('%B %d, %Y', '%B %d %Y', '%Y-%m-%d', '%d %b %Y'):
                try:
                    return datetime.strptime(raw.strip(), fmt).strftime('%Y-%m-%d')
                except ValueError:
                    continue
    return ''


def extract_website_from_text(text, fallback_url=''):
    m = WEBSITE_RE.search(text)
    if m:
        domain = m.group(0)
        if not domain.startswith('http'):
            domain = 'https://' + domain
        return domain
    return ''


def generate_context_summary(data):
    signal_type = (data.get('signal_type') or 'unknown').lower()
    stage = data.get('stage') or ''
    funding_amount = data.get('funding_amount') or ''
    job_title = data.get('job_title') or ''
    category = data.get('category') or ''
    company_name = data.get('company_name') or 'This company'

    if signal_type == 'hiring_and_funding':
        funding_part = ''
        if funding_amount and stage:
            funding_part = f"Raised a {funding_amount} {stage} round"
        elif stage:
            funding_part = f"Announced a {stage} round"
        elif funding_amount:
            funding_part = f"Raised {funding_amount} in funding"

        hiring_part = f"is hiring a {job_title}" if job_title else "is hiring for marketing/content roles"
        cat_part = f"at a {category} company" if category else ""

        parts = [p for p in [funding_part, hiring_part, cat_part] if p]
        base = ". ".join(parts[:2]) if len(parts) >= 2 else " and ".join(parts)
        return f"{base}. This suggests the company is growing and investing in market visibility."

    if signal_type == 'funding':
        if funding_amount and stage:
            base = f"Raised a {funding_amount} {stage} round"
        elif stage:
            base = f"Announced a {stage} round"
        elif funding_amount:
            base = f"Raised {funding_amount} in funding"
        else:
            base = f"{company_name} is showing funding signals"
        cat_part = f" for a {category} platform" if category else ""
        return f"{base}{cat_part}. This signals active growth and potential need for content and marketing."

    if signal_type == 'hiring':
        if job_title and stage and category:
            base = f"Hiring a {job_title} at a {stage} {category} company"
        elif job_title and category:
            base = f"Hiring a {job_title} at a {category} company"
        elif job_title:
            base = f"Hiring a {job_title}"
        else:
            base = f"{company_name} is hiring for content or marketing"
        return f"{base}. This suggests investment in content and market education."

    return f"{company_name} is showing startup market signals{' in the ' + category + ' space' if category else ''}."


def build_record_from_article(title, snippet, url, source_name, pub_date='', full_text=''):
    # Returns None if the article doesn't look like a B2B tech funding story —
    # avoids cluttering the output with consumer/lifestyle noise.
    text = ' '.join(filter(None, [title, snippet, full_text]))

    company_name = extract_company_name(title, text)
    stage = detect_stage(text)
    funding_amount = extract_funding_amount(text)
    category = classify_category(text)
    person = extract_person(text)
    person_title = extract_person_title(text) if person else ''
    funding_date = extract_funding_date(text, pub_date)

    if not is_b2b_tech(text) and not stage and not funding_amount:
        return None

    signal_type = 'funding' if (stage or funding_amount) else 'unknown'

    data = {
        'company_name': company_name,
        'website': '',
        'category': category,
        'stage': stage,
        'signal_type': signal_type,
        'signal_details': (title or snippet)[:200],
        'job_title': '',
        'funding_amount': funding_amount,
        'funding_date': funding_date,
        'relevant_person_name': person,
        'relevant_person_title': person_title,
        'source_name': source_name,
        'source_url': url,
        'context_summary': '',
        'score': 0,
        'date_found': datetime.now().strftime('%Y-%m-%d'),
    }
    data['context_summary'] = generate_context_summary(data)
    return data


def build_record_from_job(job_title, company_name, description, url, source_name, location=''):
    # Returns None if the job title doesn't match our content/marketing keywords —
    # a developer role at a startup is irrelevant even if the company is great.
    text = ' '.join(filter(None, [job_title, company_name, description]))

    stage = detect_stage(text)
    category = classify_category(text)
    matched_title = detect_job_title_match(job_title) or detect_job_title_match(text)

    if not matched_title:
        return None

    data = {
        'company_name': company_name,
        'website': '',
        'category': category,
        'stage': stage,
        'signal_type': 'hiring',
        'signal_details': f"Hiring: {job_title}" + (f" | Location: {location}" if location else ''),
        'job_title': matched_title or job_title,
        'funding_amount': '',
        'funding_date': '',
        'relevant_person_name': '',
        'relevant_person_title': '',
        'source_name': source_name,
        'source_url': url,
        'context_summary': '',
        'score': 0,
        'date_found': datetime.now().strftime('%Y-%m-%d'),
    }
    data['context_summary'] = generate_context_summary(data)
    return data
