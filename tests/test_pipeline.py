import asyncio
import copy
import json
import pytest
from verifier.models import Analysis
from verifier.pipeline import gate_judgments, validate_extraction
from verifier.providers import ProviderError
from verifier.db import dumps
from conftest import ingest

CLAIMS=[{'id':'C1','text':'Apollo 11 landed in 1972.','quote':'Apollo 11 landed on the Moon in 1972.','checkable':True,'context':'Historical date claim','queries':[]}]
QUOTE='The first landing took place on July 20, 1969.'
EVIDENCE=[{'id':'E1','status':'retrieved','text':QUOTE,'url':'https://example.org/primary-record','title':'Primary record'}]
RESULT={'summary':'A primary record contradicts the date.','judgments':[{'claim_id':'C1','verdict':'contradicted','rationale':'The event occurred in 1969.','citations':[{'evidence_id':'E1','quote':QUOTE}]}]}

@pytest.mark.parametrize('evidence,citation', [([],{'evidence_id':'E1','quote':QUOTE}),(EVIDENCE,{'evidence_id':'fabricated','quote':QUOTE}),(EVIDENCE,{'evidence_id':'E1','quote':'A quote fabricated by the AI model.'})])
def test_uncited_or_fabricated_conclusions_abstain(evidence,citation):
    result=copy.deepcopy(RESULT); result['judgments'][0]['citations']=[citation]
    gated,warnings=gate_judgments(result,CLAIMS,evidence)
    assert gated['judgments'][0]['verdict']=='unresolved' and not gated['judgments'][0]['citations']
    assert warnings

def test_challenger_insufficiency_forces_abstention():
    result,_=gate_judgments(copy.deepcopy(RESULT),CLAIMS,EVIDENCE,{'insufficient_claim_ids':['C1']})
    assert result['judgments'][0]['verdict']=='unresolved'

def test_opinion_is_not_fact_checked_as_false():
    claims=copy.deepcopy(CLAIMS); claims[0]['checkable']=False
    result,_=gate_judgments(copy.deepcopy(RESULT),claims,EVIDENCE)
    assert result['judgments'][0]['verdict']=='not_checkable'

@pytest.mark.parametrize('bad_ids',[[],['wrong'],['C1','C1']])
def test_missing_duplicate_or_invented_claims_fail_closed(bad_ids):
    result=copy.deepcopy(RESULT); result['judgments']=[{**result['judgments'][0],'claim_id':value} for value in bad_ids]
    with pytest.raises(ProviderError): gate_judgments(result,CLAIMS,EVIDENCE)

def test_extractor_cannot_invent_original_quote():
    with pytest.raises(ProviderError): validate_extraction({'claims':CLAIMS},'An entirely different post.')

def test_quote_matching_normalizes_html_spacing_but_preserves_words():
    from verifier.pipeline import normalize
    assert normalize('The event took place .')==normalize('The event took place.')
    assert normalize('An event')!=normalize('Anevent')
    validate_extraction({'claims':CLAIMS},'Apollo 11 landed on the Moon in 1972 .')

@pytest.mark.asyncio
async def test_four_agent_pipeline_and_disagreement(workspace,event,monkeypatch):
    app,client=workspace
    identifier=ingest(client,event)
    called=[]
    async def run(case_id,role,*args):
        called.append(role)
        if role=='extractor': return {'summary':'Date claim','claims':copy.deepcopy(CLAIMS)}
        if role=='challenger': return {'summary':'Primary source is direct','concerns':[],'insufficient_claim_ids':[]}
        result=copy.deepcopy(RESULT)
        if role=='adjudicator': result['judgments'][0]['verdict']='supported'
        return result
    async def gather(*args): return copy.deepcopy(EVIDENCE),[]
    monkeypatch.setattr(app.state.pipeline.providers,'run',run)
    monkeypatch.setattr(app.state.pipeline.evidence,'gather',gather)
    await app.state.pipeline.process(app.state.db.claim_job())
    case=client.get('/api/cases/'+identifier).json()
    assert case['status']=='needs_review'
    assert set(called)=={'extractor','analyst','challenger','adjudicator'}
    assert case['result']['judgments'][0]['verdict']=='conflicting_evidence'
    assert not case['result']['eligible_strike'] and not case['result']['external_actions_enabled']

@pytest.mark.asyncio
async def test_deleted_while_model_working_cannot_reappear(workspace,event,monkeypatch):
    app,client=workspace
    identifier=ingest(client,event)
    cid=client.post('/api/connections',json={'name':'local','kind':'openai_chat','base_url':'http://127.0.0.1:8087/v1','model':'test','local_endpoint':True}).json()['id']
    case=app.state.db.claim_job()
    async def complete(*args):
        ingest(client,{**event,'event_id':'delete','revision':2,'event_type':'deleted','text':''})
        return copy.deepcopy(RESULT),{}
    monkeypatch.setattr(app.state.pipeline.providers,'complete',complete)
    with pytest.raises(ProviderError):
        await app.state.pipeline.providers.run(identifier,'analyst','test',{},Analysis,False)
    detail=client.get('/api/cases/'+identifier).json()
    assert detail['status']=='deleted' and detail['runs']==[] and detail['result'] is None

@pytest.mark.asyncio
async def test_failed_primary_uses_fallback_but_never_leaks_to_hosted_model(workspace,event,monkeypatch):
    app,client=workspace
    identifier=ingest(client,event); app.state.db.claim_job()
    payload={'name':'one','kind':'openai_chat','base_url':'http://127.0.0.1:8087/v1','model':'test','local_endpoint':True}
    first=client.post('/api/connections',json=payload).json()['id']
    second=client.post('/api/connections',json={**payload,'name':'two'}).json()['id']
    client.put('/api/agents/analyst',json={'connection_id':first,'fallback_id':second})
    called=[]
    async def complete(connection,*args):
        called.append(connection['id'])
        if connection['id']==first: raise ProviderError('Quota exhausted')
        return copy.deepcopy(RESULT),{'total_tokens':30}
    monkeypatch.setattr(app.state.pipeline.providers,'complete',complete)
    result=await app.state.pipeline.providers.run(identifier,'analyst','test',{},Analysis,False)
    assert called==[first,second] and result['judgments'][0]['verdict']=='contradicted'
    app.state.db.execute('UPDATE connections SET local_endpoint=0 WHERE id=?',(second,))
    called.clear()
    with pytest.raises(ProviderError,match='not authorized'):
        await app.state.pipeline.providers.run(identifier,'analyst','test',{},Analysis,False)
    assert called==[first]
