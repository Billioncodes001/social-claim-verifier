import pytest
from fastapi.testclient import TestClient
from verifier.app import create_app

@pytest.fixture
def workspace(tmp_path):
    app = create_app(tmp_path, run_workers=False)
    with TestClient(app) as client:
        response = client.post('/api/auth/setup', json={'username':'owner', 'password':'test-password-for-this-workspace'})
        assert response.status_code == 200
        yield app, client

@pytest.fixture
def event():
    return {'event_id':'event-1', 'platform':'x', 'content_id':'post-1', 'text':'Apollo 11 landed on the Moon in 1972.',
            'author_ref':'platform-user-42', 'author_verified':True}

def ingest(client, event):
    token = client.post('/api/tokens', json={'name':'test feed'}).json()['token']
    response = client.post('/api/content-events', json=event, headers={'Authorization':'Bearer '+token})
    assert response.status_code == 202, response.text
    return response.json()['case_id']

def assessed(app, case_id):
    from verifier.db import dumps
    result = {'judgments':[{'claim_id':'C1','verdict':'contradicted','rationale':'The primary record gives a different date.',
              'citations':[{'evidence_id':'E1','quote':'The first landing took place on July 20, 1969.'}]}]}
    app.state.db.execute("UPDATE cases SET status='needs_review',result=? WHERE id=?", (dumps(result), case_id))
    return result
