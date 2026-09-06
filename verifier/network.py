"""Bounded, DNS-pinned HTTP access. Private addresses are blocked for evidence."""
import asyncio
import ipaddress
import socket
import logging
from urllib.parse import urlsplit, urljoin
import httpx

# Some OAuth providers require credentials in token-exchange query parameters.
# HTTP client diagnostics must never emit those URLs.
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

class NetworkError(Exception):
    pass

def validate_url(url, local=False):
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            raise ValueError()
        if any(ord(c) < 33 for c in url) or len(url) > 2400:
            raise ValueError()
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        if not 1 <= port <= 65535:
            raise ValueError()
        if parts.scheme == 'http' and not local:
            # Public source HTTP is allowed; keys only go to HTTPS in the provider layer.
            pass
        return parts
    except ValueError:
        raise NetworkError('Use a valid HTTP(S) URL without credentials or whitespace') from None

async def pinned_url(url, local=False):
    parts = validate_url(url, local)
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    try:
        records = await asyncio.wait_for(asyncio.to_thread(socket.getaddrinfo, parts.hostname, port, type=socket.SOCK_STREAM), 8)
        addresses = list(dict.fromkeys(row[4][0] for row in records))
    except (OSError, TimeoutError):
        raise NetworkError('Could not resolve the source host') from None
    if not addresses:
        raise NetworkError('No network address found')
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not (ip.is_loopback if local else ip.is_global and not ip.is_multicast and not ip.is_reserved):
            raise NetworkError('Private, loopback and reserved addresses are blocked for this connection')
    # Connect to a validated IP; retain the original Host and TLS name. No second DNS lookup.
    address = sorted(addresses, key=lambda value: ':' in value)[0]
    target = httpx.URL(url).copy_with(host=address)
    return target, parts.hostname, parts.netloc

async def request(method, url, *, body=None, form=None, headers=None, local=False, max_bytes=2_000_000, timeout=90):
    target, host, host_header = await pinned_url(url, local)
    request_headers = {'User-Agent': 'ClaimVerifier/0.1 (+evidence research)', 'Host': host_header, **(headers or {})}
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(timeout, connect=15), follow_redirects=False) as client:
            payload = {'data':form} if form is not None else {'json':body}
            async with client.stream(method, target, headers=request_headers, **payload,
                                     extensions={'sni_hostname': host}) as response:
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > max_bytes:
                        raise NetworkError('Response exceeded the size limit')
                return response.status_code, dict(response.headers), bytes(chunks)
    except (httpx.HTTPError, TimeoutError):
        raise NetworkError('Connection failed or timed out') from None

async def fetch(url):
    current = url
    for _ in range(4):
        status, headers, body = await request('GET', current, timeout=20)
        if status in (301, 302, 303, 307, 308):
            if 'location' not in headers:
                raise NetworkError('Redirect has no destination')
            current = urljoin(current, headers['location'])
            continue
        if status != 200:
            raise NetworkError(f'Source returned HTTP {status}')
        kind = headers.get('content-type', '').lower()
        if not any(value in kind for value in ('text/html', 'text/plain', 'application/xhtml+xml', 'application/json', 'xml')):
            raise NetworkError('Only text/HTML sources are supported in this release')
        return current, body.decode('utf-8', errors='replace'), headers
    raise NetworkError('Too many redirects')
