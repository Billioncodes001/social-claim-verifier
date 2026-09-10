import copy
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from verifier.db import dumps
from verifier.review_export import evidence_review, text_hash
from verifier.security import hash_password
from conftest import ingest

AS_OF = '2026-09-10T12:00:00+00:00'


def assessment(text='Synthetic primary record: this is captured text.', retrieved='2026-08-11T12:00:00+00:00'):
    return {'claims': [], 'judgments': [{'claim_id': 'C1', 'verdict': 'unresolved', 'citations': []}],
            'evidence': [{'id': 'E1', 'url': 'https://evidence.example.test/record?version=1', 'status': 'retrieved',
                          'text': text, 'sha256': text_hash(text), 'retrieved_at': retrieved}],
            'limitations': ['Synthetic fixture, not model accuracy.']}


@pytest.mark.parametrize(('retrieved', 'warning'), [
    ('2026-08-11T12:00:00+00:00', 'at least 30 days'),
    ('2026-08-11T12:00:01+00:00', None),
    ('2026-09-11T12:00:00+00:00', 'after the review time'),
    ('2026-09-10T12:00:00', 'missing or invalid'),
    ('invalid', 'missing or invalid'), (None, 'missing or invalid'),
])
def test_exact_freshness_boundary_and_unknown_dates(retrieved, warning):
    warnings = evidence_review(assessment(retrieved=retrieved), [], AS_OF)['sources'][0]['warnings']
    assert any(warning in w for w in warnings) if warning else not warnings


def test_integrity_and_revision_warnings_do_not_mutate_assessments():
    current, previous = assessment(), assessment('Different captured evidence text, also synthetic.')
    current['evidence'][0]['sha256'] = 'f' * 64
    original = copy.deepcopy(current)
    review = evidence_review(current, [{'id': 'previous', 'revision': 1, 'result': previous}], AS_OF)
    assert current == original
    source = review['sources'][0]
    assert any('does not match' in w for w in source['warnings'])
    assert source['source_changes'][0]['sha256'] == previous['evidence'][0]['sha256']
    previous['evidence'][0]['url'] += '&different=resource'
    assert evidence_review(current, [{'id': 'other', 'revision': 1, 'result': previous}], AS_OF)['sources'][0]['source_changes'] == []
    current['evidence'][0] = {'id': 'E1', 'status': 'unavailable'}
    assert len(evidence_review(current, [], AS_OF)['sources'][0]['warnings']) == 3


def test_packet_reproduces_saved_review_with_no_fetch_or_credential_export(workspace, event, monkeypatch):
    app, client = workspace
    def forbidden(*args, **kwargs):
        raise AssertionError('Review/export must never fetch evidence')
    monkeypatch.setattr('verifier.network.fetch', forbidden)
    first = ingest(client, event)
    prior = assessment('A previous synthetic source capture.')
    app.state.db.execute("UPDATE cases SET status='needs_review',result=? WHERE id=?", (dumps(prior), first))
    second = ingest(client, {**event, 'event_id': 'revision-2', 'revision': 2, 'event_type': 'edited'})
    current = assessment()
    app.state.db.execute("UPDATE cases SET status='needs_review',result=? WHERE id=?", (dumps(current), second))
    response = client.get(f'/api/cases/{second}/review-export', params={'as_of': AS_OF})
    assert response.status_code == 200
    packet = response.json()
    assert response.headers['content-disposition'].startswith('attachment;')
    canonical = json.dumps(packet['payload'], sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    assert packet['integrity']['sha256'] == hashlib.sha256(canonical.encode()).hexdigest()
    assert client.get(f'/api/cases/{second}/review-export', params={'as_of': AS_OF}).json() == packet
    assert packet['payload']['case']['result'] == current
    assert packet['payload']['evidence_review']['sources'][0]['source_changes'][0]['case_id'] == first
    # Looking back also identifies a changed capture in the later content revision.
    older = client.get(f'/api/cases/{first}').json()
    assert older['status'] == 'superseded'
    assert older['evidence_review']['sources'][0]['source_changes'][0]['case_id'] == second
    assert not older['can_confirm']
    assert not any(key in canonical for key in ('test-password-for-this-workspace', 'secret', 'sessions'))
    assert client.get(f'/api/cases/{second}/review-export?as_of=invalid').status_code == 422
    assert client.post(f'/api/cases/{second}/decisions', json={'decision': 'confirmed', 'reason': 'A sufficiently long review reason.'}).status_code == 422
    assert client.post(f'/api/cases/{second}/decisions', json={'decision': 'dismissed', 'reason': 'No supported conclusion in this synthetic record.'}).status_code == 200
    updated = client.get(f'/api/cases/{second}/review-export', params={'as_of': AS_OF}).json()
    assert updated['payload']['case']['review']['decision'] == 'dismissed'
    assert updated['integrity']['sha256'] != packet['integrity']['sha256']
    assert updated['payload']['case']['result'] == current
    ingest(client, {**event, 'event_id': 'revision-3', 'revision': 3, 'event_type': 'deleted'})
    deleted = client.get(f'/api/cases/{second}/review-export', params={'as_of': AS_OF}).json()
    assert deleted['payload']['case']['input']['text'] == ''
    assert deleted['payload']['case']['result'] is None
    assert deleted['payload']['case']['review'] is None
    assert deleted['payload']['evidence_review']['sources'] == []


def test_packet_keeps_role_and_private_demo_boundaries(workspace, event):
    app, client = workspace
    case = ingest(client, event)
    app.state.db.execute('INSERT INTO users VALUES(?,?,?,?)', ('reviewer-id', 'reviewer', hash_password('synthetic-reviewer-password'), 'reviewer'))
    with TestClient(app) as anonymous:
        assert anonymous.get(f'/api/cases/{case}/review-export').status_code == 401
    with TestClient(app) as reviewer:
        reviewer.post('/api/auth/login', json={'username': 'reviewer', 'password': 'synthetic-reviewer-password'})
        assert reviewer.get(f'/api/cases/{case}/review-export').status_code == 200
        assert reviewer.get('/api/connections').status_code == 403
        app.state.db.execute('UPDATE cases SET is_demo=1,owner_id=? WHERE id=?', ('another-user', case))
        assert reviewer.get(f'/api/cases/{case}/review-export').status_code == 404
        assert reviewer.get(f'/api/cases/{case}').status_code == 404
        assert client.get(f'/api/cases/{case}/review-export').status_code == 200
        app.state.db.execute('UPDATE cases SET owner_id=? WHERE id=?', ('reviewer-id', case))
        assert reviewer.get(f'/api/cases/{case}/review-export').status_code == 200
