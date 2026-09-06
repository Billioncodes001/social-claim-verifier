from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

ROLES = ('extractor', 'analyst', 'challenger', 'adjudicator')
Verdict = Literal['supported', 'contradicted', 'missing_context', 'outdated_context', 'conflicting_evidence', 'unresolved', 'not_checkable']

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Credentials(StrictModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=256)

class ConnectionInput(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal['openai_responses', 'openai_chat', 'anthropic', 'agent_endpoint']
    base_url: str = Field(max_length=500)
    model: str = Field(min_length=1, max_length=120)
    api_key: str = Field(default='', max_length=4096)
    local_endpoint: bool = False

class RoleInput(StrictModel):
    connection_id: str
    fallback_id: str | None = None

class ContentInput(StrictModel):
    event_id: str = Field(min_length=1, max_length=160)
    platform: Literal['manual', 'x', 'facebook', 'instagram', 'whatsapp', 'partner_feed', 'rss'] = 'manual'
    content_id: str = Field(min_length=1, max_length=180)
    revision: int = Field(default=1, ge=1, le=2147483647)
    event_type: Literal['created', 'edited', 'deleted'] = 'created'
    text: str = Field(default='', max_length=16000)
    author_ref: str = Field(default='', max_length=180)
    author_verified: bool = False
    source_url: str = Field(default='', max_length=2000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=6)
    allow_external_processing: bool = False
    allow_web_search: bool = False
    language: str = Field(default='en', max_length=32)

    @field_validator('text')
    @classmethod
    def text_value(cls, value):
        return value.replace('\x00', '')

class Claim(StrictModel):
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=1200)
    quote: str = Field(min_length=1, max_length=2000)
    checkable: bool
    context: str = Field(max_length=1500)
    queries: list[str] = Field(default_factory=list, max_length=2)

class Extraction(StrictModel):
    summary: str = Field(max_length=1800)
    claims: list[Claim] = Field(max_length=5)

class Citation(StrictModel):
    evidence_id: str = Field(max_length=40)
    quote: str = Field(min_length=15, max_length=700)

class Judgment(StrictModel):
    claim_id: str = Field(max_length=40)
    verdict: Verdict
    rationale: str = Field(min_length=1, max_length=2500)
    citations: list[Citation] = Field(default_factory=list, max_length=6)

class Analysis(StrictModel):
    summary: str = Field(max_length=2500)
    judgments: list[Judgment] = Field(max_length=5)

class Challenge(StrictModel):
    summary: str = Field(max_length=2500)
    concerns: list[str] = Field(max_length=8)
    insufficient_claim_ids: list[str] = Field(default_factory=list, max_length=5,
        description='ONLY claims whose truth OR falsity cannot be assessed from the evidence. A claim clearly refuted by a primary source is assessable: do NOT list it here. Return [] when the evidence settles all factual claims.')

class DecisionInput(StrictModel):
    decision: Literal['confirmed', 'dismissed', 'appealed', 'overturned']
    reason: str = Field(min_length=15, max_length=3000)
    policy_rule: str = Field(default='', max_length=300)
    incident_key: str = Field(default='', max_length=160)

class TokenInput(StrictModel):
    name: str = Field(min_length=1, max_length=80)

class SearchInput(StrictModel):
    provider: Literal['none', 'tavily', 'wikipedia'] = 'none'
    api_key: str = Field(default='', max_length=4096)

class PolicyInput(StrictModel):
    window_days: int = Field(default=180, ge=1, le=730)
    admin_threshold: int = Field(default=2, ge=2, le=10)
    senior_threshold: int = Field(default=3, ge=3, le=20)
