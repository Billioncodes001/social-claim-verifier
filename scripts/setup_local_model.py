"""Optional, pinned local smoke-test model. Downloads ~2.5 GB into .runtime only."""
import concurrent.futures
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / '.runtime' / 'local-model'
ROOT.mkdir(parents=True, exist_ok=True)
REVISION = 'bc640142c66e1fdd12af0bd68f40445458f3869b'
MODEL = 'Qwen3-4B-Q4_K_M.gguf'

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'ClaimVerifier-development'}), timeout=60)

def download(url, name, digest):
    path = ROOT / name
    if not path.exists():
        temporary = path.with_suffix(path.suffix + '.part')
        with get(url) as response, temporary.open('wb') as output:
            count = 0
            last = 0
            while chunk := response.read(4 * 1024 * 1024):
                output.write(chunk); count += len(chunk)
                if count - last > 256 * 1024 * 1024:
                    print(f'{name}: {count // 1048576} MB', flush=True); last = count
        temporary.replace(path)
    actual = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
    if actual != digest:
        raise RuntimeError(f'Hash mismatch for {name}')
    print(f'Verified {name}', flush=True)
    return path

def main():
    with get(f'https://huggingface.co/api/models/Qwen/Qwen3-4B-GGUF/tree/{REVISION}') as response:
        entries = json.load(response)
    info = next(item for item in entries if item['path'] == MODEL)
    sha = info['lfs']['oid']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        binary = pool.submit(download, 'https://github.com/ggml-org/llama.cpp/releases/download/b10819/llama-b10819-bin-win-vulkan-x64.zip', 'llama.zip', '4c5ff97b5440024906fc90f67809d84b92d9b77847c7d1a800701a36499e565e')
        model = pool.submit(download, f'https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/{REVISION}/{MODEL}', MODEL, sha)
        archive = binary.result()
        with zipfile.ZipFile(archive) as z:
            destination = (ROOT / 'server').resolve()
            for name in z.namelist():
                if not (destination / name).resolve().is_relative_to(destination):
                    raise RuntimeError('Unsafe archive path')
            z.extractall(destination)
        model.result()
    (ROOT / 'provenance.json').write_text(json.dumps({'llama_release': 'b10819', 'model_repository': 'Qwen/Qwen3-4B-GGUF', 'model_revision': REVISION, 'model': MODEL, 'model_sha256': sha, 'license': 'Apache-2.0', 'purpose': 'Local integration testing, not a calibrated misinformation detector'}, indent=2))
    print('Local model files ready.', flush=True)

if __name__ == '__main__': main()
