# Max possible score is 130. Leads scoring 80+ are considered high-priority.
# The weights reflect that "hiring_and_funding" together is the strongest signal —
# it means the company just raised and is actively building out their marketing team.
SEED_STAGES = {'seed', 'pre-seed'}
SERIES_A_STAGES = {'series a'}
CONTENT_HIRING_TITLES = {
    'content marketer', 'head of content', 'content lead', 'social media manager',
    'videographer', 'video editor', 'creative strategist', 'growth marketer',
    'vp growth', 'demand gen manager', 'marketing manager', 'head of marketing',
    'cmo', 'brand marketing', 'founder brand', 'executive brand',
    'content marketing manager', 'director of content', 'content strategist',
    'digital marketing manager',
}
B2B_TECH_CATEGORIES = {
    'ai', 'saas', 'b2b saas', 'devops', 'cloud', 'cybersecurity', 'data',
    'analytics', 'automation', 'vertical saas', 'infrastructure', 'api',
    'fintech', 'healthtech', 'hr tech', 'developer tools', 'machine learning',
    'data platform', 'security', 'workflow automation',
}


def score_company(data):
    score = 0
    stage = (data.get('stage') or '').lower()
    signal_type = (data.get('signal_type') or '').lower()
    job_title = (data.get('job_title') or '').lower()
    category = (data.get('category') or '').lower()
    funding_amount = data.get('funding_amount') or ''
    funding_date = data.get('funding_date') or ''
    person_name = data.get('relevant_person_name') or ''

    # Early-stage companies are the best fit — they're growing fast and haven't
    # yet built out a content function. Series B+ often have in-house teams.
    if stage in SEED_STAGES or stage in SERIES_A_STAGES:
        score += 30

    # Funding presence (even just a date) confirms a real round was announced,
    # not just a rumor or a job posting from an underfunded company.
    if funding_amount or funding_date:
        score += 30

    # A content/marketing job title match is the most direct buying signal —
    # they're actively looking for this type of work and budgeting for it.
    if any(t in job_title for t in CONTENT_HIRING_TITLES) or job_title in CONTENT_HIRING_TITLES:
        score += 30

    if any(cat in category for cat in B2B_TECH_CATEGORIES) or category in B2B_TECH_CATEGORIES:
        score += 20

    # Bonus for the rare case where both signals appear: company just raised AND
    # is hiring content/marketing. This is the hottest possible lead.
    if signal_type == 'hiring_and_funding':
        score += 40

    # Named founder/exec means there's a specific person to cold-email.
    if person_name.strip():
        score += 10

    return score
