import asyncio
import hashlib
import json
from urllib.parse import quote, urlsplit
from bs4 import BeautifulSoup
from . import network
from .db import now

class Evidence:
    def __init__(self, db, vault):
        self.db, self.vault = db, vault

    async def search(self, query):
        setting = self.db.setting('search', {'provider': 'none'})
        provider = setting['provider']
        if provider == 'none':
            return []
        if provider == 'tavily':
            secret = self.vault.decrypt(setting.get('secret', ''))
            if not secret:
                raise network.NetworkError('Tavily search has no API key')
            status, _, raw = await network.request('POST', 'https://api.tavily.com/search', body={
                'query': query[:400], 'search_depth': 'basic', 'max_results': 3,
                'include_answer': False, 'include_raw_content': False},
                headers={'Authorization': 'Bearer ' + secret}, timeout=25)
            if status != 200:
                raise network.NetworkError(f'Search returned HTTP {status}')
            result = json.loads(raw)
            return [row['url'] for row in result.get('results', []) if isinstance(row.get('url'), str)][:3]
        # No-key background source, explicitly not a comprehensive current-news search.
        url = 'https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=' + quote(query[:250]) + '&srlimit=3&format=json'
        status, _, raw = await network.request('GET', url, timeout=20)
        if status != 200:
            raise network.NetworkError(f'Background search returned HTTP {status}')
        result = json.loads(raw)
        return ['https://en.wikipedia.org/wiki/' + quote(row['title'].replace(' ', '_')) for row in result.get('query', {}).get('search', [])]

    async def page(self, url, number):
        record = {'id': f'E{number}', 'url': url, 'retrieved_at': now(), 'status': 'unavailable'}
        try:
            final, html, headers = await network.fetch(url)
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.title.get_text(' ', strip=True) if soup.title else urlsplit(final).hostname
            date = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('meta', attrs={'name': 'date'})
            published = date.get('content') if date else None
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'svg']):
                tag.decompose()
            main = soup.find('main') or soup.find('article') or soup.body or soup
            text = ' '.join(main.get_text(' ', strip=True).split())[:28000]
            if len(text) < 80:
                raise network.NetworkError('Source did not expose enough readable text')
            record.update({'status': 'retrieved', 'url': final, 'title': title[:300], 'text': text,
                           'published_at': published, 'host': urlsplit(final).hostname,
                           'sha256': hashlib.sha256(text.encode()).hexdigest(), 'method': 'Direct bounded HTTP fetch; HTML text extraction'})
        except (network.NetworkError, ValueError) as exc:
            record['error'] = str(exc)
        return record

    async def gather(self, content, extraction):
        urls = list(content['evidence_urls'])
        notices = []
        if content['allow_web_search']:
            queries = list(dict.fromkeys(q for claim in extraction['claims'] for q in claim['queries']))[:3]
            results = await asyncio.gather(*(self.search(q) for q in queries), return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    notices.append('A search request failed or was unavailable')
                else:
                    urls.extend(result)
            provider = self.db.setting('search', {'provider': 'none'})['provider']
            if provider == 'none':
                notices.append('Search is not configured; only supplied evidence URLs were checked')
            elif provider == 'wikipedia':
                notices.append('Background search is limited to English Wikipedia, not comprehensive current-news verification')
        else:
            notices.append('Web search was not authorized; only supplied evidence URLs were checked')
        urls = list(dict.fromkeys(urls))[:8]
        semaphore = asyncio.Semaphore(3)
        async def one(url, n):
            async with semaphore:
                return await self.page(url, n)
        records = await asyncio.gather(*(one(url, n+1) for n, url in enumerate(urls)))
        seen = set()
        for record in records:
            if record['status'] == 'retrieved':
                if record['sha256'] in seen:
                    record['duplicate_content'] = True
                seen.add(record['sha256'])
        return records, notices
