"""Read-only review packets from local captures; never fetch or revise verdicts."""
import hashlib
import json
from datetime import datetime, timezone
from fastapi import HTTPException

STALE_DAYS = 30
LIMITS = [
    'Local saved evidence only. No live source or social-account check is performed.',
    'Capture age is a review reminder, not a truth, publication-age or source-quality score.',
    'Source changes compare exact URLs in the nearest earlier and latest later saved assessments of this content. Other URLs and investigations are not compared.',
    'Hashes cover extracted text, not the entire source page. Matching text does not prove a source is current or accurate.',
    'Agent outputs and citation matches are not factual certification. Human review and abstention rules remain unchanged.',
    'This packet is not a database backup, signed attestation or guarantee that a model run can be replayed. Downloaded copies cannot be recalled after deletion.',
]


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def evidence_review(result, related, as_of):
    checked = timestamp(as_of)
    if checked is None:
        raise HTTPException(422, 'as_of must be an ISO timestamp with a timezone')
    sources = []
    for source in (result or {}).get('evidence', []):
        warnings, changes = [], []
        retrieved = timestamp(source.get('retrieved_at'))
        age = (checked - retrieved).total_seconds() / 86400 if retrieved else None
        if source.get('status') != 'retrieved':
            warnings.append('Source unavailable; no retrieved evidence to assess.')
        if retrieved is None:
            warnings.append('Capture time is missing or invalid; freshness is unknown.')
        elif age < 0:
            warnings.append('Capture time is after the review time; check the clock or chosen as-of time.')
        elif age >= STALE_DAYS:
            warnings.append('Capture is at least 30 days old; review whether newer evidence is needed.')
        text = source.get('text')
        computed = text_hash(text) if isinstance(text, str) else None
        if not source.get('sha256') or computed is None:
            warnings.append('Captured text or its hash is missing; integrity cannot be checked.')
        elif source['sha256'] != computed:
            warnings.append('Stored hash does not match captured text; investigate integrity before relying on this source.')
        for other in related:
            for previous in (other['result'] or {}).get('evidence', []):
                if (source.get('url') and source.get('url') == previous.get('url') and
                    source.get('status') == previous.get('status') == 'retrieved' and
                    computed and isinstance(previous.get('text'), str) and
                    computed != text_hash(previous['text'])):
                    changes.append({'case_id': other['id'], 'revision': other['revision'],
                                    'evidence_id': previous.get('id'), 'sha256': text_hash(previous['text']),
                                    'retrieved_at': previous.get('retrieved_at')})
        if changes:
            warnings.append('Different captured text exists at this exact URL in another saved content revision. Review the change; it does not establish a correction.')
        sources.append({'evidence_id': source.get('id'), 'age_days': round(age, 3) if age is not None else None,
                        'computed_sha256': computed, 'warnings': warnings, 'source_changes': changes})
    return {'as_of': checked.isoformat(), 'stale_after_days': STALE_DAYS, 'sources': sources,
            'related_revisions': [{'case_id': r['id'], 'revision': r['revision']} for r in related],
            'limits': LIMITS}


def review_snapshot(db, case_id, actor, as_of):
    # One SQLite read transaction keeps captures, review and source revisions coherent.
    with db.connect() as tx:
        tx.execute('BEGIN')
        found = tx.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
        if not found or (found['is_demo'] and actor['role'] != 'admin' and found['owner_id'] != actor['id']):
            raise HTTPException(404, 'Case not found')
        row = dict(found)
        row['input'] = json.loads(row['input'])
        row['result'] = json.loads(row['result']) if row['result'] else None
        row['runs'] = [dict(r) for r in tx.execute('SELECT * FROM runs WHERE case_id=? ORDER BY created,id', (case_id,))]
        for run in row['runs']:
            for key in ('output', 'usage'):
                run[key] = json.loads(run[key]) if run[key] else None
        review = tx.execute('SELECT * FROM reviews WHERE case_id=?', (case_id,)).fetchone()
        row['review'] = dict(review) if review else None
        related = []
        for comparison in ('<', '>'):
            other = tx.execute(f'''SELECT id,revision,result FROM cases WHERE platform=? AND content_id=?
                AND revision {comparison} ? AND result IS NOT NULL AND status!='deleted'
                AND is_demo=? AND (is_demo=0 OR owner_id IS ?) ORDER BY revision DESC LIMIT 1''',
                (row['platform'], row['content_id'], row['revision'], row['is_demo'], row['owner_id'])).fetchone()
            if other:
                related.append(dict(other) | {'result': json.loads(other['result'])})
        row['evidence_review'] = evidence_review(row['result'], related, as_of)
        return row


def review_packet(snapshot):
    payload = {'schema': 'claim-verifier-human-review/v1',
               'case': {k: snapshot[k] for k in ('id', 'platform', 'content_id', 'revision', 'status', 'stage',
                        'created', 'updated', 'is_demo', 'author_ref', 'author_verified', 'input', 'result', 'runs', 'review', 'error')},
               'evidence_review': snapshot['evidence_review']}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return {'payload': payload, 'integrity': {
        'algorithm': 'sha256', 'sha256': text_hash(canonical),
        'canonicalization': 'UTF-8 json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(\",\", \":\"), allow_nan=False)',
        'scope': 'payload only; unkeyed checksum detects accidental changes, not authenticity'}}
