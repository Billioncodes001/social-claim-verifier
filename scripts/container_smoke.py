"""Exercise an actual generated installation over HTTP, without printing credentials."""
import argparse
import json
from pathlib import Path
import time
import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',default='.deployment')
    parser.add_argument('--report',default='artifacts/container-validation.json')
    parser.add_argument('--after-restart',action='store_true')
    args=parser.parse_args()
    bundle=Path(args.bundle)
    installation=json.loads((bundle/'installation.json').read_text())
    with httpx.Client(base_url=installation['url'],timeout=15) as client:
        for attempt in range(40):
            try:
                response=client.get('/healthz')
                if response.status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(1)
        else:raise RuntimeError('Container did not become healthy')
        assert response.json()['version']=='0.2.0'
        assert client.get('/api/demo').status_code==401
        assert client.get('/api/auth/status').json()['setup_required'] is False
        secret=(bundle/'secrets/admin_password').read_text().strip()
        login={'username':installation['username'],'password':secret}
        assert client.post('/api/auth/setup',json=login).status_code==403
        assert client.post('/api/auth/login',json=login).status_code==200
        workspace=client.get('/api/workspace').json()
        if args.after_restart:
            assert workspace['workspace']['organization']=='Container validation workspace'
        assert len(workspace['platforms'])==7
        assert len(client.get('/api/demo').json()['platforms'])==3
        assert client.get('/api/social/apps').status_code==200
        assert client.get('/readyz').status_code==503  # A model has not been connected yet.
        response=client.put('/api/workspace',json={**workspace['workspace'],'organization':'Container validation workspace'})
        assert response.status_code==200
        assert client.get('/api/workspace').json()['workspace']['organization']=='Container validation workspace'
        report={'version':'0.2.0','passed':True,'checks':['actual image startup','automatic admin bootstrap','setup endpoint closed',
            'authenticated UI APIs','workspace persistence','unconfigured agents reported not ready'],
            'restart_verified':args.after_restart,
            'limits':'No social credentials or model API were supplied to this container test.'}
        target=Path(args.report);target.parent.mkdir(exist_ok=True,parents=True)
        target.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))


if __name__=='__main__':main()
