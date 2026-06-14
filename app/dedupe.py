import re
from urllib.parse import urlparse


# Two records are considered the same company if their domain matches OR their
# normalized name matches. Domain wins when available because names like
# "Acme AI" and "Acme AI Inc." normalize to the same string.

def normalize_domain(url):
    if not url:
        return ''
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        domain = re.sub(r'^www\.', '', domain)
        return domain
    except Exception:
        return url.lower()


def normalize_name(name):
    if not name:
        return ''
    name = name.lower().strip()
    name = re.sub(r'\b(inc|llc|ltd|corp|co|company|technologies|technology|solutions|platform|platforms)\b\.?', '', name)
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def _merge(existing, new_record):
    # When the same company appears in both a funding article and a job listing,
    # combine both into one record and upgrade signal_type to 'hiring_and_funding'.
    merged = dict(existing)
    for key, val in new_record.items():
        if val and not merged.get(key):
            merged[key] = val
        elif key == 'score' and val:
            merged[key] = max(merged.get(key, 0), val)
        elif key == 'source_url' and val and merged.get(key) and val not in merged[key]:
            merged[key] = merged[key] + ' | ' + val
        elif key == 'signal_type' and val and merged.get(key):
            types = {merged[key], val}
            if 'funding' in types and 'hiring' in types:
                merged[key] = 'hiring_and_funding'
        elif key == 'job_title' and val and merged.get(key) and val not in merged[key]:
            merged[key] = merged[key] + ' / ' + val
    return merged


def deduplicate(records):
    seen_domains = {}
    seen_names = {}
    deduped = []

    for rec in records:
        domain = normalize_domain(rec.get('website', ''))
        name = normalize_name(rec.get('company_name', ''))

        matched_key = None
        if domain and domain in seen_domains:
            matched_key = ('domain', domain)
        elif name and name in seen_names:
            matched_key = ('name', name)

        if matched_key:
            kind, key = matched_key
            if kind == 'domain':
                idx = seen_domains[key]
            else:
                idx = seen_names[key]
            deduped[idx] = _merge(deduped[idx], rec)
        else:
            idx = len(deduped)
            deduped.append(dict(rec))
            if domain:
                seen_domains[domain] = idx
            if name:
                seen_names[name] = idx

    return deduped
