"""Generate an isolated customer Compose bundle. Requires only Python's standard library."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets


def build_bundle(output, *, domain='', port=8791, username='admin', project_root=None):
    if domain and (len(domain)>253 or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}', domain)):
        raise ValueError('Use a DNS hostname such as claims.example.com, without a scheme, port or path')
    if not 1024<=port<=65535: raise ValueError('Port must be between 1024 and 65535')
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,80}',username): raise ValueError('Use 3–80 letters, numbers, underscores or hyphens for the administrator name')
    output = Path(output).resolve()
    project_root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    # Refuse to replace any bundle: its secrets may already encrypt customer data.
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    (output/'.gitignore').write_text('*\n',encoding='utf-8')
    secret_dir=output/'secrets'
    secret_dir.mkdir(mode=0o700)
    for name,value in [('admin_password',secrets.token_urlsafe(24)),('master_key',base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())]:
        with os.fdopen(os.open(secret_dir/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as handle:
            handle.write(value+'\n')
    origin='https://'+domain if domain else 'http://127.0.0.1:'+str(port)
    app={'build':{'context':str(project_root)},'image':'claim-verifier:0.2.0',
         'depends_on':{'initialize':{'condition':'service_completed_successfully'}},
         'volumes':['verifier-data:/data'],
         'environment':{'VERIFIER_PUBLIC_URL':origin,'VERIFIER_ALLOWED_HOSTS':','.join(filter(None,[domain,'localhost','127.0.0.1'])),
                        'VERIFIER_DISABLE_WEB_SETUP':'1','VERIFIER_SECURE_COOKIES':'1' if domain else '0',
                        'VERIFIER_WORKERS':'2','VERIFIER_QUEUE_LIMIT':'100'},
         'restart':'unless-stopped','read_only':True,'tmpfs':['/tmp'],
         'cap_drop':['ALL'],'security_opt':['no-new-privileges:true']}
    if not domain: app['ports']=['127.0.0.1:'+str(port)+':8791']
    config={'name':'claim-verifier-'+secrets.token_hex(3),'services':{
        'initialize':{'build':{'context':str(project_root)},'image':'claim-verifier:0.2.0','user':'0:0',
                      'entrypoint':['python','-m','verifier.initialize'],'network_mode':'none',
                      'volumes':['verifier-data:/data'],'secrets':['admin_password','master_key'],
                      'environment':{'VERIFIER_BOOTSTRAP_PASSWORD_FILE':'/run/secrets/admin_password',
                                     'VERIFIER_BOOTSTRAP_USERNAME':username},
                      'read_only':True,'tmpfs':['/tmp'],'restart':'no',
                      'security_opt':['no-new-privileges:true']},
        'verifier':app},'volumes':{'verifier-data':{}},
        'secrets':{name:{'file':'./secrets/'+name} for name in ['admin_password','master_key']}}
    if domain:
        (output/'Caddyfile').write_text(domain+' {\n  reverse_proxy verifier:8791\n}\n',encoding='utf-8')
        config['services']['https']={'image':'caddy:2-alpine','ports':['80:80','443:443'],
            'volumes':['./Caddyfile:/etc/caddy/Caddyfile:ro','caddy-data:/data','caddy-config:/config'],
            'depends_on':{'verifier':{'condition':'service_healthy'}},'restart':'unless-stopped'}
        config['volumes'].update({'caddy-data':{},'caddy-config':{}})
    # JSON is a YAML subset accepted by Docker Compose, avoiding interpolation/quoting mistakes.
    (output/'compose.yaml').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    (output/'installation.json').write_text(json.dumps({'url':origin,'username':username,'version':'0.2.0'},indent=2)+'\n',encoding='utf-8')
    (output/'START.txt').write_text(
        'Start: docker compose -f "'+str(output/'compose.yaml')+'" up -d --build\n'
        'Open: '+origin+'\nAdministrator: '+username+'\n'
        'Read the password locally from secrets/admin_password. Never commit or share this directory.\n'
        'Connect a model API in Connections; test it, then configure Agent team and Evidence search.\n'
        'Read /readyz after agent assignment. It checks configuration, not model accuracy.\n'
        'Back up the volume and secrets together. Never delete the volume to upgrade.\n',encoding='utf-8')
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='.deployment')
    parser.add_argument('--domain',default='',help='Enable automatic HTTPS for this DNS hostname')
    parser.add_argument('--port',type=int,default=8791,help='Local-only host port when --domain is omitted')
    parser.add_argument('--username',default='admin')
    args=parser.parse_args()
    try: output=build_bundle(args.output,domain=args.domain,port=args.port,username=args.username)
    except (ValueError,FileExistsError) as exc: parser.error(str(exc))
    print('Installation bundle: '+str(output))
    print('Next: docker compose -f "'+str(output/'compose.yaml')+'" up -d --build')
    print('Login instructions: '+str(output/'START.txt'))


if __name__=='__main__': main()
