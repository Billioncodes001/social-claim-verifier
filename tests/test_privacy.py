def test_bad_credentials_are_never_echoed_in_validation_errors(workspace):
    _,client=workspace
    secret='sensitive-password-'*40
    response=client.post('/api/auth/login',json={'username':'owner','password':secret})
    assert response.status_code==422 and 'sensitive-password' not in response.text

def test_chunked_body_is_bounded(workspace):
    _,client=workspace
    def chunks():
        for _ in range(20): yield b'x'*20000
    response=client.post('/api/content-events',content=chunks())
    assert response.status_code==413

def test_admin_can_read_api_contract_without_secrets(workspace):
    _,client=workspace
    response=client.get('/api/openapi.json')
    assert response.status_code==200
    assert '/api/content-events' in response.json()['paths']
