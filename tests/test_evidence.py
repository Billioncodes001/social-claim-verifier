import pytest
from verifier import network

@pytest.mark.asyncio
async def test_redirect_to_metadata_is_blocked(monkeypatch):
    original=network.request
    async def redirect(method,url,**kwargs):
        if url=='https://source.example/': return 302,{'location':'http://169.254.169.254/latest/meta-data/'},b''
        return await original(method,url,**kwargs)
    monkeypatch.setattr(network,'request',redirect)
    with pytest.raises(network.NetworkError,match='blocked'): await network.fetch('https://source.example/')

@pytest.mark.asyncio
async def test_duplicate_sources_are_marked_and_scripts_removed(workspace,monkeypatch):
    app,_=workspace
    async def fetch(url):
        return url,'<html><title>Record</title><script>INJECTED_COMMAND</script><main>The official public record establishes that this event happened on the recorded historical date and at the named location.</main></html>',{}
    monkeypatch.setattr(network,'fetch',fetch)
    result,notices=await app.state.pipeline.evidence.gather({'evidence_urls':['https://a.example','https://b.example'],'allow_web_search':False},{'claims':[]})
    assert len(result)==2 and result[1]['duplicate_content']
    assert 'INJECTED_COMMAND' not in result[0]['text']
    assert len(result[0]['sha256'])==64

@pytest.mark.asyncio
async def test_source_failure_is_an_explicit_unavailable_record(workspace,monkeypatch):
    app,_=workspace
    async def fetch(url): raise network.NetworkError('Source returned HTTP 403')
    monkeypatch.setattr(network,'fetch',fetch)
    record=await app.state.pipeline.evidence.page('https://example.com',1)
    assert record['status']=='unavailable' and 'text' not in record and '403' in record['error']

@pytest.mark.asyncio
async def test_tavily_protocol_returns_urls_not_generated_answers(workspace,monkeypatch):
    app,_=workspace
    app.state.db.set_setting('search',{'provider':'tavily','secret':app.state.vault.encrypt('test-search-key')})
    seen={}
    async def request(method,url,**kwargs):
        seen.update(method=method,url=url,**kwargs)
        return 200,{},b'{"answer":"Do not use this generated answer","results":[{"url":"https://example.com/record","content":"A snippet is not source evidence"}]}'
    monkeypatch.setattr(network,'request',request)
    urls=await app.state.pipeline.evidence.search('A factual query')
    assert urls==['https://example.com/record']
    assert seen['headers']['Authorization']=='Bearer test-search-key'
    assert seen['body']['include_answer'] is False and seen['url']=='https://api.tavily.com/search'

@pytest.mark.asyncio
async def test_search_does_not_run_without_submission_permission(workspace,monkeypatch):
    app,_=workspace
    async def search(query): raise AssertionError('Unauthorized search query was transmitted')
    monkeypatch.setattr(app.state.pipeline.evidence,'search',search)
    sources,notices=await app.state.pipeline.evidence.gather({'evidence_urls':[],'allow_web_search':False},{'claims':[{'queries':['private content']} ]})
    assert sources==[] and notices
