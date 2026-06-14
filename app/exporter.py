import csv
import os
from datetime import datetime

FIELDS = [
    'company_name', 'website', 'category', 'stage', 'signal_type',
    'signal_details', 'job_title', 'funding_amount', 'funding_date',
    'relevant_person_name', 'relevant_person_title', 'source_name',
    'source_url', 'context_summary', 'score', 'date_found', 'priority_tier',
]

# Seed and Series A with score >= 70 are "High". Everything else is "Low".
# Pre-Seed, Series B+, unknown stage, and low-scoring records are always "Low".
_HIGH_STAGES = {'seed', 'series a'}


def _priority_tier(rec):
    stage = (rec.get('stage') or '').lower()
    score = rec.get('score') or 0
    if stage in _HIGH_STAGES and score >= 70:
        return 'High'
    return 'Low'


def export_to_csv(records, date_str=None, export_dir="data/exports"):
    os.makedirs(export_dir, exist_ok=True)
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    path = os.path.join(export_dir, f"startup_signal_dump_{date_str}.csv")

    for rec in records:
        rec['priority_tier'] = _priority_tier(rec)

    sorted_records = sorted(
        records,
        key=lambda r: (
            0 if r.get('priority_tier') == 'High' else 1,  # High tier first
            -(r.get('score') or 0),
            r.get('funding_date') or '',
            r.get('signal_type') or '',
        )
    )

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        writer.writeheader()
        for rec in sorted_records:
            writer.writerow({f: rec.get(f, '') for f in FIELDS})

    return path, len(sorted_records)
