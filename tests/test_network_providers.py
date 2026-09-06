import json
import socket
import pytest
from verifier import network
from verifier.providers import Providers, ProviderError, parse_object

@pytest.mark.parametrize('address',['127.0.0.1','10.0.0.1','169.254.169.254','192.168.1.1','0.0.0.0','::1','fe80::1','224.0.0.1'])
@pytest.mark.asyncio
async def test_evidence_cannot_reach_private_network(address,monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',(address,443))])
    with pytest.raises(network.NetworkError): await network.pinned_url('https://source.example/')

@pytest.mark.asyncio
async def test_mixed_dns_answer_is_rejected(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',('93.184.216.34',443)),(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(network.NetworkError): await network.pinned_url('https://source.example/')

@pytest.mark.asyncio
async def test_pinned_address_retains_hostname(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',('93.184.216.34',443))])
    target,sni,host=await network.pinned_url('https://source.example:443/a?q=1')
    assert target.host=='93.184.216.34' and sni=='source.example' and host=='source.example:443'
    assert target.path=='/a' and target.query==b'q=1'

@pytest.mark.parametrize('kind',['openai_responses','openai_chat','anthropic','agent_endpoint'])
@pytest.mark.asyncio
async def test_provider_wire_protocols(workspace,kind,monkeypatch):
    app,_=workspace
    provider=app.state.pipeline.providers
    connection={'base_url':'https://api.example/v1','local_endpoint':False,'secret':app.state.vault.encrypt('test-key'),'kind':kind,'model':'model'}
    seen={}
    async def request(method,url,**kwargs):
        seen.update(method=method,url=url,**kwargs)
        outputs={'openai_responses':{'status':'completed','output':[{'content':[{'type':'output_text','text':'{"ok":true}'}]}]},
                 'openai_chat':{'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]},
                 'anthropic':{'stop_reason':'end_turn','content':[{'type':'text','text':'{"ok":true}'}]},
                 'agent_endpoint':{'result':{'ok':True}}}
        return 200,{},json.dumps(outputs[kind]).encode()
    monkeypatch.setattr(network,'request',request)
    value,usage=await provider.complete(connection,'probe','Instructions',{'post':'test'},{'type':'object'})
    assert value=={'ok':True} and seen['method']=='POST'
    if kind=='openai_responses': assert seen['body']['store'] is False and seen['url'].endswith('/responses')
    if kind=='anthropic': assert seen['headers']['x-api-key']=='test-key' and 'Authorization' not in seen['headers']
    if kind=='agent_endpoint': assert seen['body']['role']=='probe' and 'response_schema' in seen['body']

@pytest.mark.asyncio
async def test_provider_error_body_does_not_leak(workspace,monkeypatch):
    app,_=workspace
    async def request(*args,**kwargs): return 401,{},b'Your secret API credential: PRIVATE_KEY'
    monkeypatch.setattr(network,'request',request)
    connection={'base_url':'https://api.example/v1','local_endpoint':False,'secret':'','kind':'openai_chat','model':'m'}
    with pytest.raises(ProviderError) as error: await app.state.pipeline.providers.complete(connection,'probe','',{}, {})
    assert 'PRIVATE_KEY' not in str(error.value) and '401' in str(error.value)

@pytest.mark.parametrize('value',['not JSON','[]','{"x":1} trailing'])
def test_malformed_json_rejected(value):
    with pytest.raises(ProviderError): parse_object(value)
