import json
from datetime import datetime, timezone, timedelta
from .configuration import profile

DEFAULT = {'window_days': 180, 'admin_threshold': 2, 'senior_threshold': 3}

def account_state(db, platform, author):
    config = profile(db, platform)['policy'] or db.setting('policy', DEFAULT)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=config['window_days'])).isoformat()
    rows = db.all('''SELECT c.id,r.incident_key,r.updated FROM cases c JOIN reviews r ON c.id=r.case_id
        WHERE c.platform=? AND c.author_ref=? AND c.author_verified=1 AND c.is_demo=0
        AND c.status='reviewed' AND r.decision='confirmed' AND c.created>=?''', (platform, author, cutoff))
    count = len({row['incident_key'] for row in rows if row['incident_key']})
    tier = 'senior_review' if count >= config['senior_threshold'] else 'admin_review' if count >= config['admin_threshold'] else 'monitor'
    return {'platform': platform, 'author_ref': author, 'eligible_incidents': count, 'escalation': tier,
            'automatic_account_disabling': False, 'window_days': config['window_days']}

def can_confirm(case):
    if case.get('is_demo'):
        return False
    if not case['author_verified'] or not case['author_ref']:
        return False
    result = case['result'] or {}
    if isinstance(result, str):
        result = json.loads(result)
    return any(j['verdict'] in ('contradicted', 'missing_context', 'outdated_context') and j.get('citations') for j in result.get('judgments', []))
