import re
import os

_CATEGORIES = None
_JOB_TITLES = None

# Order matters: pre-seed must come before seed so it doesn't get swallowed
# by the generic \bseed\b pattern.
STAGE_PATTERNS = [
    (re.compile(r'\bpre[- ]?seed\b', re.I), 'Pre-Seed'),
    (re.compile(r'\bseries\s+a\b', re.I), 'Series A'),
    (re.compile(r'\bseries\s+b\b', re.I), 'Series B'),
    (re.compile(r'\bseed\s+(?:round|funding|stage|extension)\b', re.I), 'Seed'),
    (re.compile(r'\bseed\b', re.I), 'Seed'),
]

B2B_SIGNALS = [
    'b2b', 'enterprise', 'saas', 'platform', 'api', 'cloud', 'devops',
    'cybersecurity', 'security', 'data', 'analytics', 'automation',
    'infrastructure', 'software', 'developer', 'fintech', 'healthtech',
    'hr tech', 'hrtech', 'workflow', 'integration', 'compliance',
    'monitoring', 'observability', 'ai', 'machine learning', 'ml',
]

CONSUMER_SIGNALS = [
    'restaurant', 'retail', 'ecommerce', 'e-commerce', 'real estate',
    'creator', 'agency', 'consumer app', 'gaming', 'dating', 'social media app',
    'marketplace for consumers', 'fashion', 'food delivery', 'ride sharing',
]


def _load_categories():
    global _CATEGORIES
    if _CATEGORIES is None:
        path = "config/categories.txt"
        if os.path.exists(path):
            # Preserve original case from config — categories.txt already has
            # correct capitalisation (AI, SaaS, HR Tech, etc.). Lowercasing here
            # was the root cause of "Ai" being stored instead of "AI".
            with open(path) as f:
                _CATEGORIES = [l.strip() for l in f if l.strip()]
        else:
            _CATEGORIES = [
                'AI', 'SaaS', 'B2B SaaS', 'DevOps', 'Cloud', 'Cybersecurity',
                'Data', 'Analytics', 'Automation', 'Vertical SaaS',
                'Infrastructure', 'API', 'Fintech', 'Healthtech', 'HR Tech',
            ]
    return _CATEGORIES


def _load_job_titles():
    global _JOB_TITLES
    if _JOB_TITLES is None:
        path = "config/job_titles.txt"
        if os.path.exists(path):
            with open(path) as f:
                _JOB_TITLES = [l.strip().lower() for l in f if l.strip()]
        else:
            _JOB_TITLES = [
                'content marketer', 'head of content', 'content lead',
                'social media manager', 'videographer', 'video editor',
                'creative strategist', 'growth marketer', 'vp growth',
                'demand gen manager', 'marketing manager', 'head of marketing',
                'cmo', 'brand marketing', 'founder brand', 'executive brand',
            ]
    return _JOB_TITLES


def detect_stage(text):
    if not text:
        return ''
    for pattern, stage in STAGE_PATTERNS:
        if pattern.search(text):
            return stage
    return ''


def classify_category(text):
    if not text:
        return ''
    text_lower = text.lower()
    categories = _load_categories()

    category_keywords = {
        'AI': ['artificial intelligence', ' ai ', 'ai-', 'machine learning', 'llm', 'generative', 'gpt', 'deep learning', 'nlp'],
        'Cybersecurity': ['cybersecurity', 'security', 'cyber', 'soc', 'threat', 'vulnerability', 'compliance', 'zero trust'],
        'DevOps': ['devops', 'devsecops', 'ci/cd', 'kubernetes', 'docker', 'deployment', 'platform engineering'],
        'Data': ['data platform', 'data pipeline', 'data warehouse', 'data lake', 'etl', 'analytics platform'],
        'Fintech': ['fintech', 'financial technology', 'payments', 'banking', 'lending', 'insurance tech', 'insurtech'],
        'Healthtech': ['healthtech', 'health tech', 'healthcare', 'medtech', 'clinical', 'patient', 'ehr', 'medical'],
        'HR Tech': ['hr tech', 'hrtech', 'human resources', 'recruiting', 'talent', 'workforce', 'payroll', 'benefits'],
        'Cloud': ['cloud', 'aws', 'azure', 'gcp', 'multi-cloud', 'cloud-native', 'infrastructure'],
        'Automation': ['automation', 'workflow', 'no-code', 'low-code', 'robotic process', 'rpa', 'orchestration'],
        'API': ['api', 'developer platform', 'sdk', 'integration', 'webhook', 'developer tool'],
        'SaaS': ['saas', 'software as a service', 'subscription software'],
        'B2B SaaS': ['b2b saas', 'b2b software', 'enterprise software', 'business software'],
        'Vertical SaaS': ['vertical saas', 'industry-specific', 'vertical software'],
        'Infrastructure': ['infrastructure', 'platform infrastructure', 'cloud infrastructure', 'networking'],
    }

    for cat, keywords in category_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                return cat

    # Match against text_lower but return the category in its original case
    # from the config file (avoids "Ai", "Api", "B2B Saas", etc.)
    for cat in categories:
        if cat.lower() in text_lower:
            return cat

    return ''


def is_b2b_tech(text):
    if not text:
        return False
    text_lower = text.lower()

    # Consumer signals are hard disqualifiers — reject before counting B2B signals
    # so a "social media app for restaurants" doesn't sneak through on 'app'.
    for sig in CONSUMER_SIGNALS:
        if sig in text_lower:
            return False

    b2b_count = sum(1 for sig in B2B_SIGNALS if sig in text_lower)
    return b2b_count >= 1


def detect_job_title_match(text):
    if not text:
        return ''
    text_lower = text.lower()
    titles = _load_job_titles()
    for title in titles:
        if title in text_lower:
            return title.title()
    return ''
