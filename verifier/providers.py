import asyncio
import json
import re
import time
from urllib.parse import urlsplit
from pydantic import ValidationError
from . import network
from .db import dumps, uid, now

class ProviderError(Exception):
    pass

def decoding_schema(value):
    # Large character repetitions make llama.cpp's grammar exponential. Keep
    # structural constraints in decoding; Pydantic still enforces all lengths.
    if isinstance(value, dict):
        return {key: decoding_schema(item) for key, item in value.items() if key not in ('minLength', 'maxLength', 'title', 'default')}
    if isinstance(value, list):
        return [decoding_schema(item) for item in value]
    return value

def parse_object(text):
    if not isinstance(text, str):
        raise ProviderError('Provider did not return text')
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        raise ProviderError('Provider returned invalid JSON; no verdict accepted') from None
    if not isinstance(value, dict):
        raise ProviderError('Provider JSON must be an object')
    return value

class Providers:
    def __init__(self, db, vault):
        self.db, self.vault = db, vault

    async def complete(self, connection, role, instructions, payload, schema):
        if role in ('analyst', 'adjudicator') and 'claims' in payload:
            schema = json.loads(dumps(schema))
            count = len(payload['claims'])
            schema['properties']['judgments'].update(minItems=count, maxItems=count)
            if count:
                schema['$defs']['Judgment']['properties']['claim_id']['enum'] = [item['id'] for item in payload['claims']]
        base = connection['base_url'].rstrip('/')
        local = bool(connection['local_endpoint'])
        parts = network.validate_url(base, local)
        if not local and parts.scheme != 'https':
            raise ProviderError('Hosted AI endpoints require HTTPS')
        secret = self.vault.decrypt(connection['secret'])
        headers = {'Content-Type': 'application/json'}
        if secret:
            headers['Authorization'] = 'Bearer ' + secret
        system = instructions + '\nReturn ONLY a JSON object matching this schema. No Markdown or hidden reasoning.\n' + dumps(schema)
        user = dumps(payload)
        kind = connection['kind']
        if kind == 'openai_responses':
            endpoint = base + '/responses'
            body = {'model': connection['model'], 'instructions': system, 'input': user, 'store': False,
                    'max_output_tokens': 3000, 'text': {'format': {'type': 'json_object'}}}
        elif kind == 'anthropic':
            endpoint = base + '/messages'
            headers.pop('Authorization', None)
            headers.update({'x-api-key': secret, 'anthropic-version': '2023-06-01'})
            body = {'model': connection['model'], 'max_tokens': 3000, 'system': system,
                    'messages': [{'role': 'user', 'content': user}]}
        elif kind == 'agent_endpoint':
            endpoint = base
            body = {'role': role, 'instructions': instructions, 'input': payload, 'response_schema': schema}
        else:
            endpoint = base + '/chat/completions'
            body = {'model': connection['model'], 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                    'max_tokens': 3000, 'response_format': {'type': 'json_object'}}
            if local:
                body['response_format'] = {'type': 'json_object', 'schema': decoding_schema(schema)}
                body['chat_template_kwargs'] = {'enable_thinking': False}
                body['temperature'] = 0.2
        for attempt in range(3):
            try:
                status, _, raw = await network.request('POST', endpoint, body=body, headers=headers, local=local, timeout=120)
            except network.NetworkError as exc:
                if attempt == 2:
                    raise ProviderError(str(exc)) from None
                await asyncio.sleep(0.4 * (attempt + 1))
                continue
            if status in (429, 500, 502, 503, 504) and attempt < 2:
                await asyncio.sleep(0.7 * (attempt + 1))
                continue
            if status < 200 or status >= 300:
                # Never return a provider's raw error body (it may echo credentials or input).
                raise ProviderError(f'Provider returned HTTP {status}. Check the model, credentials and quota.')
            try:
                result = json.loads(raw)
                if kind == 'agent_endpoint':
                    value = result['result']
                    if not isinstance(value, dict):
                        raise ValueError()
                    return value, result.get('usage', {})
                if kind == 'openai_responses':
                    if result.get('status') not in (None, 'completed'):
                        raise ProviderError('Model response was incomplete; no verdict accepted')
                    text = ''.join(part.get('text', '') for item in result.get('output', []) for part in item.get('content', []) if part.get('type') == 'output_text')
                elif kind == 'anthropic':
                    if result.get('stop_reason') == 'max_tokens':
                        raise ProviderError('Model response exceeded its output budget')
                    text = ''.join(part.get('text', '') for part in result.get('content', []) if part.get('type') == 'text')
                else:
                    choice = result['choices'][0]
                    if choice.get('finish_reason') == 'length':
                        raise ProviderError('Model response exceeded its output budget')
                    text = choice['message']['content']
                return parse_object(text), result.get('usage', {})
            except (KeyError, ValueError, TypeError, IndexError):
                raise ProviderError('Provider response did not match its protocol') from None
        raise ProviderError('Provider retry budget exhausted')

    async def run(self, case_id, role, instructions, payload, output_model, allow_external):
        mapping = self.db.one('SELECT * FROM roles WHERE role=?', (role,))
        if not mapping:
            raise ProviderError(f'No connection assigned to {role}. Configure agents in Connections.')
        errors = []
        for connection_id in dict.fromkeys([mapping['connection_id'], mapping['fallback_id']]):
            if not connection_id:
                continue
            conn = self.db.one('SELECT * FROM connections WHERE id=?', (connection_id,))
            if not conn:
                errors.append('Assigned connection was removed')
                continue
            if not conn['local_endpoint'] and not allow_external:
                errors.append('External model processing was not authorized for this submission')
                continue
            run_id, started = uid(), time.monotonic()
            inserted = self.db.execute("INSERT INTO runs(id,case_id,role,status,connection_id,model,created) SELECT ?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM cases WHERE id=? AND status='processing')",
                            (run_id, case_id, role, 'running', connection_id, conn['model'], now(), case_id))
            if not inserted:
                raise ProviderError('Content is no longer available for investigation')
            try:
                value, usage = await self.complete(conn, role, instructions, payload, output_model.model_json_schema())
                validated = output_model.model_validate(value).model_dump()
                written = self.db.execute("UPDATE runs SET status='complete',output=?,usage=?,elapsed_ms=? WHERE id=? AND EXISTS(SELECT 1 FROM cases WHERE id=? AND status='processing')",
                                (dumps(validated), dumps(usage), int((time.monotonic() - started)*1000), run_id, case_id))
                if not written:
                    raise ProviderError('Content was superseded or deleted during model processing')
                return validated
            except asyncio.CancelledError:
                self.db.execute("UPDATE runs SET status='interrupted',error='Investigation stopped' WHERE id=?", (run_id,))
                raise
            except (ProviderError, ValidationError) as exc:
                message = str(exc) if isinstance(exc, ProviderError) else 'AI output failed schema validation; no verdict accepted'
                self.db.execute("UPDATE runs SET status='failed',error=?,elapsed_ms=? WHERE id=?", (message, int((time.monotonic()-started)*1000), run_id))
                errors.append(message)
        raise ProviderError('; '.join(errors) or f'{role} has no usable connection')
