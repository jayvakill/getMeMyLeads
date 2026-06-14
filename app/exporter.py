import csv
import os
from datetime import datetime

FIELDS = [
    'company_name', 'website', 'category', 'stage', 'signal_type',
    'signal_details', 'job_title', 'funding_amount', 'funding_date',
    'relevant_person_name', 'relevant_person_title', 'source_name',
    'source_url', 'context_summary', 'score', 'date_found',
]


def export_to_csv(records, date_str=None, export_dir="data/exports"):
    os.makedirs(export_dir, exist_ok=True)
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    path = os.path.join(export_dir, f"startup_signal_dump_{date_str}.csv")

    sorted_records = sorted(
        records,
        key=lambda r: (-(r.get('score') or 0), r.get('funding_date') or '', r.get('signal_type') or '')
    )

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        writer.writeheader()
        for rec in sorted_records:
            writer.writerow({f: rec.get(f, '') for f in FIELDS})

    return path, len(sorted_records)
